# simplypy/daemon.py
import os
import sys
import socket
import subprocess
import time
from pathlib import Path
from filelock import FileLock   # pip install filelock — wraps flock/Windows correctly

from silloncommon.socket_path import get_socket_path, get_lockfile_path, get_pidfile_path

STARTUP_TIMEOUT = 10.0   # seconds to wait for daemon to become ready
POLL_INTERVAL   = 0.05   # seconds between readiness polls

def _is_pid_alive(pid: int) -> bool:
    # NOTE: minor PID-reuse race possible after crash + OS PID recycling.
    # Acceptable for a local dev tool; revisit if it becomes a problem.
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _try_connect(socket_path: Path) -> socket.socket | None:
    """Attempt a single connection. Returns socket on success, None on failure."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(str(socket_path))
        return s
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        return None


def _wait_until_ready(socket_path: Path, timeout: float) -> bool:
    """Poll until the daemon accepts connections or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        s = _try_connect(socket_path)
        if s is not None:
            s.close()
            return True
        time.sleep(POLL_INTERVAL)
    return False


def _spawn_daemon(project_path: str, socket_path: Path, pid_file: Path):
    """Spawn a detached daemon process."""
    log_path = Path(project_path) / ".sillon" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Launch via the current interpreter so the daemon always runs in the same
    # environment as the client, regardless of whether the console script is on
    # PATH (works from an unactivated venv, a fresh checkout, pytest, etc.).
    cmd = [sys.executable, "-m", "silloncore.server.main", project_path]

    with open(log_path, "a") as log_file:
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                creationflags=flags,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,   # detach from parent's process group
                close_fds=True,
            )

    # Write PID so we can check liveness later
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(proc.pid))


def ensure_daemon(project_path: str) -> None:
    """
    Ensure a daemon is running for this project.
    Safe to call from multiple processes simultaneously.
    """
    socket_path = get_socket_path(project_path)
    pid_file    = get_pidfile_path(project_path)
    lock_file   = get_lockfile_path(project_path)

    Path(project_path, ".sillon").mkdir(parents=True, exist_ok=True)

    # Fast path: daemon already up
    if socket_path.exists():
        s = _try_connect(socket_path)
        if s is not None:
            s.close()
            return   # already running, nothing to do

        # Socket file exists but connection refused — check if PID is alive
        if pid_file.exists():
            pid = int(pid_file.read_text().strip())
            if _is_pid_alive(pid):
                # Still starting up, just wait
                if _wait_until_ready(socket_path, STARTUP_TIMEOUT):
                    return
                raise RuntimeError("Daemon exists but did not become ready in time")

        # Stale socket/pid — clean up and fall through to spawn
        socket_path.unlink(missing_ok=True)
        pid_file.unlink(missing_ok=True)

    # Slow path: need to spawn — use a lock so two processes don't both spawn
    with FileLock(str(lock_file), timeout=STARTUP_TIMEOUT):
        # Re-check inside the lock (another process may have spawned while we waited)
        s = _try_connect(socket_path)
        if s is not None:
            s.close()
            return

        _spawn_daemon(project_path, socket_path, pid_file)

        if not _wait_until_ready(socket_path, STARTUP_TIMEOUT):
            raise RuntimeError(
                f"Daemon failed to start. Check logs at "
                f"{Path(project_path) / '.sillon' / 'daemon.log'}"
            )
