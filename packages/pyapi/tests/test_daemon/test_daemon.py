"""Daemon-level tests: the REGISTER auth handshake and the PID liveness probe.

These drive a real auto-spawned daemon over whichever transport is active, so
they cover the wire behaviour that `test_transport.py` deliberately does not.
"""

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from silloncommon import transport
from silloncommon.commands import DumpCmd
from silloncommon.framing import send_msg, recv_msg
from silloncommon.rpcHandler import RPCHandler
from sillonpy.daemon import _is_pid_alive, ensure_daemon

CURRENT_PATH = Path(__file__).parent.resolve()
SILLON_PATH = CURRENT_PATH / ".sillon"


@pytest.fixture(scope="module", autouse=True)
def clean_workspace():
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH)

    ensure_daemon(str(CURRENT_PATH))

    yield

    # Ask the daemon to stop, then let it release the endpoint before we delete
    # the project dir (Windows will not remove a directory with open handles).
    time.sleep(1)
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH, ignore_errors=True)


def _client():
    sock = transport.connect(str(CURRENT_PATH))
    assert sock is not None, "daemon should be accepting connections"
    return sock


def _register(sock, token):
    """Send a hand-built REGISTER frame and return the decoded result."""
    handler = RPCHandler()
    msg = json.dumps(
        {
            "jsonrpc": handler.JSONRPC_VERSION,
            "method": "REGISTER",
            "params": json.dumps(
                {
                    "auth_token": token,
                    "run_id": str(uuid.uuid4()),
                    "run_name": "auth-probe",
                    "project_name": "auth-project",
                    "platform": "test_platform",
                    "hostname": "test_host",
                    "organisation": "org",
                    "author": "author",
                    "project_path": str(CURRENT_PATH),
                }
            ),
            "id": 0,
        }
    )
    send_msg(sock, msg.encode("utf-8"))
    return handler.decode_response(recv_msg(sock).decode("utf-8"))["result"]


# ==========================================
#            REGISTER AUTH
# ==========================================


def test_register_succeeds_with_the_published_token():
    sock = _client()
    try:
        result = _register(sock, transport.read_token(str(CURRENT_PATH)))
        assert result["ack"] is True
    finally:
        sock.close()


# The daemon reports failures as a *top-level* JSON-RPC "error", which
# decode_response raises on -- so a rejection surfaces as an exception rather
# than as a value tucked inside "result". These tests assert that shape.


def test_register_is_rejected_with_a_wrong_token():
    sock = _client()
    try:
        with pytest.raises(Exception, match="AuthenticationFailed"):
            _register(sock, "0" * 64)
    finally:
        sock.close()


def test_register_is_rejected_with_no_token():
    sock = _client()
    try:
        with pytest.raises(Exception, match="AuthenticationFailed"):
            _register(sock, None)
    finally:
        sock.close()


def test_commands_are_rejected_before_register():
    """A connection that skips REGISTER must not be able to issue commands."""
    sock = _client()
    try:
        encoded = RPCHandler().encode_request(DumpCmd(), 0, str(uuid.uuid4()))
        send_msg(sock, encoded.encode("utf-8"))
        with pytest.raises(Exception, match="AuthenticationFailed"):
            RPCHandler().decode_response(recv_msg(sock).decode("utf-8"))
    finally:
        sock.close()


# ==========================================
#            PID LIVENESS PROBE
# ==========================================


def test_pid_probe_reports_a_live_process():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert _is_pid_alive(proc.pid) is True
    finally:
        proc.kill()
        proc.wait()


def test_pid_probe_reports_a_dead_process():
    """Must return False rather than raising -- and must not kill anything.

    The POSIX `os.kill(pid, 0)` idiom is a no-op probe; on Windows the same call
    routes to TerminateProcess, which is why this has a platform branch.
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    assert _is_pid_alive(proc.pid) is False


def test_pid_probe_does_not_kill_its_target():
    """Regression guard for the os.kill(pid, 0) footgun on Windows."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        for _ in range(3):
            assert _is_pid_alive(proc.pid) is True
        assert proc.poll() is None, "liveness probe terminated the process"
    finally:
        proc.kill()
        proc.wait()
