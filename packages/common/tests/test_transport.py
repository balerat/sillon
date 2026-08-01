"""Transport-layer tests.

These run against *both* transports on every platform. The `unix` case is
skipped where `socket.AF_UNIX` does not exist (Windows); the `tcp` case always
runs, which is what gives POSIX CI coverage of the Windows code path.
"""

import shutil
import pathlib
import socket
import tempfile
import threading

import pytest

from silloncommon import transport
from silloncommon.framing import send_msg, recv_msg
from silloncommon.socket_path import (
    get_socket_path,
    get_portfile_path,
    get_tokenfile_path,
)

TRANSPORTS = ["unix", "tcp"]


@pytest.fixture
def project_dir():
    """A project directory with a short path.

    Not `tmp_path`: pytest nests it under `pytest-of-<user>/pytest-N/<testname>`,
    which blows past the ~104-byte `sun_path` limit an AF_UNIX socket address
    has. Real project directories are nowhere near that deep, but the fixture
    has to stay under it for the `unix` leg to bind at all.
    """
    root = pathlib.Path(tempfile.mkdtemp(prefix="sil"))
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(params=TRANSPORTS)
def pinned_transport(request, monkeypatch):
    """Force a transport for the duration of a test."""
    if request.param == "unix" and not hasattr(socket, "AF_UNIX"):
        pytest.skip("socket.AF_UNIX unavailable on this platform")
    monkeypatch.setenv("SILLON_TRANSPORT", request.param)
    return request.param


# ==========================================
#           TRANSPORT SELECTION
# ==========================================


def test_selection_follows_interpreter_capability(monkeypatch):
    monkeypatch.delenv("SILLON_TRANSPORT", raising=False)
    assert transport.use_unix_socket() is hasattr(socket, "AF_UNIX")


def test_override_forces_tcp(monkeypatch):
    monkeypatch.setenv("SILLON_TRANSPORT", "tcp")
    assert transport.use_unix_socket() is False
    assert transport.describe_transport() == "tcp"


def test_invalid_override_is_rejected(monkeypatch):
    monkeypatch.setenv("SILLON_TRANSPORT", "carrier-pigeon")
    with pytest.raises(ValueError):
        transport.use_unix_socket()


# ==========================================
#             ENDPOINT FILES
# ==========================================


def test_endpoint_files_match_transport(pinned_transport, project_dir):
    sock = transport.create_listener(project_dir)
    try:
        # The token always exists; it is what authorises a REGISTER.
        assert get_tokenfile_path(project_dir).exists()
        assert transport.endpoint_exists(project_dir)

        if pinned_transport == "unix":
            assert get_socket_path(project_dir).exists()
            assert not get_portfile_path(project_dir).exists()
        else:
            assert get_portfile_path(project_dir).exists()
            assert not get_socket_path(project_dir).exists()
            # The published port must be the one we are actually listening on.
            published = int(get_portfile_path(project_dir).read_text(encoding="utf-8"))
            assert published == sock.getsockname()[1]
    finally:
        sock.close()
        transport.clear_endpoint(project_dir)

    assert not transport.endpoint_exists(project_dir)
    assert transport.read_token(project_dir) is None


def test_connect_returns_none_without_a_daemon(pinned_transport, project_dir):
    (project_dir / ".sillon").mkdir()
    assert transport.connect(project_dir) is None


def test_connect_returns_none_on_stale_endpoint(pinned_transport, project_dir):
    """A crash leftover must read as 'no daemon', not raise."""
    sock = transport.create_listener(project_dir)
    sock.close()   # daemon dies, endpoint files survive
    assert transport.connect(project_dir) is None


def test_create_listener_clears_a_stale_endpoint(pinned_transport, project_dir):
    first = transport.create_listener(project_dir)
    first_token = transport.read_token(project_dir)
    first.close()

    second = transport.create_listener(project_dir)
    try:
        # A fresh daemon must mint a fresh secret, not inherit the dead one.
        assert transport.read_token(project_dir) != first_token
        assert transport.connect(project_dir) is not None
    finally:
        second.close()
        transport.clear_endpoint(project_dir)


def test_clear_endpoint_is_idempotent(pinned_transport, project_dir):
    (project_dir / ".sillon").mkdir()
    transport.clear_endpoint(project_dir)   # nothing to remove
    transport.clear_endpoint(project_dir)


# ==========================================
#               ROUND TRIP
# ==========================================


def test_framed_round_trip(pinned_transport, project_dir):
    """A full framed exchange over whichever transport is selected."""
    listener = transport.create_listener(project_dir)
    received = []

    def echo_once():
        conn, _ = listener.accept()
        with conn:
            payload = recv_msg(conn)
            received.append(payload)
            send_msg(conn, b"pong:" + payload)

    server = threading.Thread(target=echo_once, daemon=True)
    server.start()

    client = transport.connect(project_dir)
    assert client is not None
    try:
        send_msg(client, b"ping")
        assert recv_msg(client) == b"pong:ping"
    finally:
        client.close()
        server.join(timeout=5)
        listener.close()
        transport.clear_endpoint(project_dir)

    assert received == [b"ping"]


def test_large_frame_round_trip(pinned_transport, project_dir):
    """Frames larger than one TCP segment must reassemble correctly."""
    listener = transport.create_listener(project_dir)
    payload = b"x" * (1024 * 512)

    def echo_once():
        conn, _ = listener.accept()
        with conn:
            send_msg(conn, recv_msg(conn))

    server = threading.Thread(target=echo_once, daemon=True)
    server.start()

    client = transport.connect(project_dir)
    try:
        send_msg(client, payload)
        assert recv_msg(client) == payload
    finally:
        client.close()
        server.join(timeout=10)
        listener.close()
        transport.clear_endpoint(project_dir)
