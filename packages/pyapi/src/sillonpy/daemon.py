# sillonpy/daemon.py
import ctypes
import os
import sys
import subprocess
import time
from pathlib import Path
from filelock import FileLock  # pip install filelock — wraps flock/Windows correctly

from silloncommon import transport
from silloncommon.socket_path import get_lockfile_path, get_pidfile_path

STARTUP_TIMEOUT = 10.0   # seconds to wait for daemon to become ready
POLL_INTERVAL   = 0.05   # seconds between readiness polls


def _is_pid_alive(pid: int) -> bool:
    # NOTE: minor PID-reuse race possible after crash + OS PID recycling.
    # Acceptable for a local dev tool; revisit if it becomes a problem.
    if sys.platform == "win32":
        return _is_pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _is_pid_alive_windows(pid: int) -> bool:
    """Windows liveness probe.

    ``os.kill(pid, 0)`` must never be used here: on Windows every signal other
    than CTRL_C_EVENT/CTRL_BREAK_EVENT is routed to TerminateProcess, so the
    POSIX "signal 0 is a no-op probe" idiom would kill the daemon outright.
    Windows also raises a plain OSError (WinError 87) for a dead PID rather than
    ProcessLookupError.

    Instead, open a handle and poll it: a process handle becomes signalled when
    the process exits, so WAIT_TIMEOUT means "still running". This is preferred
    over GetExitCodeProcess, which reports a process that legitimately exited
    with code 259 (STILL_ACTIVE) as alive.
    """
    SYNCHRONIZE = 0x00100000
    WAIT_TIMEOUT = 0x00000102

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return False   # no such process, or it is already gone
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _wait_until_ready(project_path: str, timeout: float) -> bool:
    """Poll until the daemon accepts connections or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        s = transport.connect(project_path)
        if s is not None:
            s.close()
            return True
        time.sleep(POLL_INTERVAL)
    return False


def _spawn_daemon(project_path: str, pid_file: Path):
    """Spawn a detached daemon process."""
    log_path = Path(project_path) / ".sillon" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Launch via the current interpreter so the daemon always runs in the same
    # environment as the client, regardless of whether the console script is on
    # PATH (works from an unactivated venv, a fresh checkout, pytest, etc.).
    cmd = [sys.executable, "-u", "-m", "silloncore.server.main", project_path]

    with open(log_path, "a", encoding="utf-8") as log_file:
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
                start_new_session=True,  # detach from parent's process group
                close_fds=True,
            )

    # Write PID so we can check liveness later
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(proc.pid), encoding="utf-8")


def ensure_daemon(project_path: str) -> None:
    """
    Ensure a daemon is running for this project.
    Safe to call from multiple processes simultaneously.
    """
    pid_file  = get_pidfile_path(project_path)
    lock_file = get_lockfile_path(project_path)

    Path(project_path, ".sillon").mkdir(parents=True, exist_ok=True)

    # Fast path: daemon already up
    if transport.endpoint_exists(project_path):
        s = transport.connect(project_path)
        if s is not None:
            s.close()
            return  # already running, nothing to do

        # Endpoint published but connection refused — check if PID is alive
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                pid = None
            if pid is not None and _is_pid_alive(pid):
                # Still starting up, just wait
                if _wait_until_ready(project_path, STARTUP_TIMEOUT):
                    return
                raise RuntimeError("Daemon exists but did not become ready in time")

        # Stale endpoint/pid — clean up and fall through to spawn
        transport.clear_endpoint(project_path)
        pid_file.unlink(missing_ok=True)

    # Slow path: need to spawn — use a lock so two processes don't both spawn
    with FileLock(str(lock_file), timeout=STARTUP_TIMEOUT):
        # Re-check inside the lock (another process may have spawned while we waited)
        s = transport.connect(project_path)
        if s is not None:
            s.close()
            return

        _spawn_daemon(project_path, pid_file)

        if not _wait_until_ready(project_path, STARTUP_TIMEOUT):
            raise RuntimeError(
                f"Daemon failed to start. Check logs at "
                f"{Path(project_path) / '.sillon' / 'daemon.log'}"
            )
