"""Shared helpers for the portability suites, which drive the real daemon.

These tests create, rename and delete project directories, and they reuse the
same short paths (the AF_UNIX socket path cap leaves little room). That makes
one thing mandatory: **never touch a project directory while its daemon is
still serving it.**

A daemon lives for `SILLON_IDLE_TIMEOUT` after its last client. Remove the
directory under it and the next test recreates the same path, where a stale
`daemon.sock` may still be connectable -- a moved or recreated Unix socket
keeps its inode, so the client reaches the *old* daemon, which is still
holding the old storage root. That is a flake that looks like a logic bug and
reproduces about one run in ten.
"""

import os
from pathlib import Path

import pytest

from silloncommon.socket_path import get_pidfile_path

# Short, so waiting for a daemon to exit costs a second rather than the
# five-minute default. Below about a second the daemon's loop, which ticks
# once per second, can race a client that is still connecting.
IDLE = 1.0

# Every subprocess in these suites runs with this, so a daemon goes away
# promptly rather than lingering for the five-minute default.
CHILD_ENV = {**os.environ, "SILLON_IDLE_TIMEOUT": str(IDLE)}


def wait_for_daemon_to_go(project, timeout: float = IDLE + 25) -> None:
    """Block until the project's daemon has exited.

    Watched through the pidfile rather than by connecting: a probe connection
    counts as activity and resets the idle timer, so polling the socket keeps
    the daemon alive forever. (Cost me a two-minute test timeout to find.)

    Returns immediately when no daemon was ever recorded.
    """
    import time

    pid_file = get_pidfile_path(str(project))
    try:
        pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.25)
    pytest.fail(f"daemon {pid} for {project} never exited")


def release(*projects) -> None:
    """Wait for each project's daemon, so the directory can be moved or removed."""
    for project in projects:
        if Path(project).exists():
            wait_for_daemon_to_go(project)
