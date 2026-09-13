"""The daemon must go away when nothing is using it.

Regression guard: connections used to be registered EVENT_READ|EVENT_WRITE. An
idle socket with an empty send buffer is always writable, so sel.select()
returned instantly forever -- the daemon spun at 100% CPU and the idle branch,
which only runs when select() times out, was never reached.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from silloncommon import transport

CURRENT_PATH = Path(__file__).parent.resolve()
PROJECT = CURRENT_PATH / "_idle_project"

IDLE = 3.0           # the daemon's configured idle timeout for these tests
GRACE = 12.0         # generous headroom: the loop ticks once a second


@pytest.fixture(autouse=True)
def clean_project():
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    PROJECT.mkdir(parents=True)
    yield
    time.sleep(0.3)
    if PROJECT.exists():
        shutil.rmtree(PROJECT, ignore_errors=True)


def _start_daemon():
    env = {**os.environ, "SILLON_IDLE_TIMEOUT": str(IDLE)}
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "silloncore.server.main", str(PROJECT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        probe = transport.connect(str(PROJECT))
        if probe is not None:
            probe.close()
            return proc
        time.sleep(0.05)
    proc.kill()
    pytest.fail("daemon did not become ready")


def _attach_silently():
    """A client that connects and then says nothing at all."""
    sock = transport.connect(str(PROJECT))
    assert sock is not None, "could not attach to the daemon"
    return sock


def _wait_for_exit(proc, timeout):
    try:
        proc.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        return False


def test_daemon_exits_after_idle_timeout():
    proc = _start_daemon()
    try:
        assert _wait_for_exit(proc, IDLE + GRACE), "idle daemon never shut down"
    finally:
        proc.kill()


def test_silent_client_does_not_keep_the_daemon_alive():
    """A connection that is open but says nothing must not defeat the timeout."""
    proc = _start_daemon()
    silent = _attach_silently()       # connect, then never send anything
    try:
        assert _wait_for_exit(proc, IDLE + GRACE), (
            "a silent connection kept the daemon alive - EVENT_WRITE is "
            "probably back in accept_wrapper"
        )
    finally:
        silent.close()
        proc.kill()


def test_daemon_does_not_busy_spin_while_a_client_is_attached():
    """CPU must stay near zero; the bug pinned a whole core."""
    psutil = pytest.importorskip("psutil")

    proc = _start_daemon()
    silent = _attach_silently()
    try:
        handle = psutil.Process(proc.pid)
        handle.cpu_percent(None)      # prime the measurement
        time.sleep(1.5)
        cpu = handle.cpu_percent(None)
        assert cpu < 25, f"daemon busy-spinning at {cpu}% CPU with an idle client"
    finally:
        silent.close()
        proc.kill()
