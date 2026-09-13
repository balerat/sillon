"""Platform-agnostic stream transport for the sillon daemon.

The daemon and its clients speak length-prefixed JSON-RPC over a connected
``SOCK_STREAM`` socket. *How* that socket is obtained is the only thing that
differs between platforms, and this module is the single place where that
difference lives.

Two transports
--------------
``unix``  AF_UNIX socket at ``.sillon/daemon.sock``. The historical (and still
          the default) transport. Access control comes from the filesystem.

``tcp``   AF_INET socket bound to ``127.0.0.1`` on an ephemeral port, with the
          port published in ``.sillon/daemon.port``. Used where ``AF_UNIX`` is
          unavailable -- which today means Windows: CPython does not expose
          ``socket.AF_UNIX`` on Windows in any released version (3.14/3.15
          included, see cpython issue #77589), even though the OS itself has
          supported Unix sockets since Windows 10 1803.

Selection is by capability (``hasattr(socket, "AF_UNIX")``), not by
``sys.platform``, so if CPython ever ships Unix sockets on Windows this module
starts using them with no code change. ``SILLON_TRANSPORT=unix|tcp`` forces a
transport, which is what lets POSIX CI exercise the Windows path.

Authentication
--------------
A loopback TCP port is reachable by *any* local process, so the daemon writes a
random secret to ``.sillon/daemon.token`` and every client must echo it in its
REGISTER frame. The check is enforced on both transports: it costs nothing on
AF_UNIX and it closes the pre-existing hole where any user able to traverse the
project directory could connect to the socket and issue ``shutdown``.
"""

import os
import secrets
import socket

from pathlib import Path

from silloncommon.socket_path import (
    get_socket_path,
    get_portfile_path,
    get_tokenfile_path,
)

_HAS_AF_UNIX = hasattr(socket, "AF_UNIX")


def use_unix_socket() -> bool:
    """Whether this process should speak AF_UNIX rather than loopback TCP.

    Honours the ``SILLON_TRANSPORT`` environment variable (``unix`` or ``tcp``)
    so tests can pin a transport; otherwise falls back to what the interpreter
    actually supports.
    """
    override = os.environ.get("SILLON_TRANSPORT")
    if override:
        override = override.strip().lower()
        if override == "unix":
            if not _HAS_AF_UNIX:
                raise RuntimeError(
                    "SILLON_TRANSPORT=unix but this Python has no socket.AF_UNIX"
                )
            return True
        if override == "tcp":
            return False
        raise ValueError(
            f"Invalid SILLON_TRANSPORT={override!r} (expected 'unix' or 'tcp')"
        )
    return _HAS_AF_UNIX


def describe_transport() -> str:
    """Human-readable transport name, for log lines."""
    return "unix" if use_unix_socket() else "tcp"


# ==========================================
#               ENDPOINT FILES
# ==========================================


def endpoint_exists(project_path) -> bool:
    """Whether a daemon endpoint has been published for this project.

    This is a *discovery* check, not a liveness check -- the endpoint may well
    be a crash leftover. Callers follow it with :func:`connect`.
    """
    if use_unix_socket():
        return get_socket_path(project_path).exists()
    return get_portfile_path(project_path).exists()


def clear_endpoint(project_path) -> None:
    """Remove every endpoint file for this project. Safe to call when absent."""
    for path in (
        get_socket_path(project_path),
        get_portfile_path(project_path),
        get_tokenfile_path(project_path),
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Windows refuses to unlink a file another process still holds open.
            # Nothing useful to do here: either the daemon is alive (and the
            # endpoint is not stale after all) or the next run retries.
            pass


def read_token(project_path) -> str | None:
    """Read the daemon's shared secret. ``None`` if no daemon has published one."""
    try:
        return get_tokenfile_path(project_path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _write_private(path: Path, content: str) -> None:
    """Write a small endpoint file, owner-readable only where that's meaningful."""
    path.write_text(content, encoding="utf-8")
    if os.name == "posix":
        os.chmod(path, 0o600)


# ==========================================
#                  SERVER
# ==========================================


def create_listener(project_path) -> socket.socket:
    """Create, bind and listen on the daemon's endpoint, then publish it.

    Publication order matters. The endpoint file is what makes the daemon
    discoverable to clients, so it must not become visible until the daemon can
    actually accept connections, and the token must exist before the endpoint
    does:

    * AF_UNIX -- ``bind()`` itself creates ``daemon.sock``, so the token is
      written first.
    * TCP -- ``daemon.port`` is written last, after ``listen()``.

    Returns the listening socket, still in blocking mode; the caller sets
    non-blocking and registers it with its selector.
    """
    sillon_dir = Path(project_path) / ".sillon"
    sillon_dir.mkdir(parents=True, exist_ok=True)

    # Clear any crash leftover before binding.
    clear_endpoint(project_path)

    _write_private(get_tokenfile_path(project_path), secrets.token_hex(32))

    if use_unix_socket():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(get_socket_path(project_path)))
            sock.listen()
        except OSError:
            sock.close()
            raise
        return sock

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Deliberately no SO_REUSEADDR: we bind an ephemeral port, so there is
        # nothing to reuse, and on Windows SO_REUSEADDR lets an unrelated
        # process bind the same address out from under us.
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        _write_private(get_portfile_path(project_path), str(sock.getsockname()[1]))
    except OSError:
        sock.close()
        raise
    return sock


# ==========================================
#                  CLIENT
# ==========================================


def connect(project_path) -> socket.socket | None:
    """Attempt a single connection to the project's daemon.

    Returns a connected socket, or ``None`` if the endpoint is missing,
    unreadable, or refusing connections -- callers poll on ``None`` rather than
    handling errors individually.
    """
    sock = None
    try:
        if use_unix_socket():
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(str(get_socket_path(project_path)))
        else:
            port_text = get_portfile_path(project_path).read_text(encoding="utf-8")
            port = int(port_text.strip())
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Request/response protocol with small frames: Nagle would add
            # ~40ms of latency to every single log call.
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.connect(("127.0.0.1", port))
        return sock
    except (OSError, ValueError):
        # OSError covers ConnectionRefusedError / FileNotFoundError; ValueError
        # covers a truncated or half-written port file.
        if sock is not None:
            sock.close()
        return None
