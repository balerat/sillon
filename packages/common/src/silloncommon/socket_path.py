from pathlib import Path

def get_socket_path(project_path: str) -> Path:
    """AF_UNIX endpoint. Only used on platforms that expose ``socket.AF_UNIX``."""
    return Path(project_path) / ".sillon" / "daemon.sock"

def get_portfile_path(project_path: str) -> Path:
    """Loopback-TCP endpoint: holds the ephemeral port the daemon is listening on.

    Only used on platforms without ``socket.AF_UNIX`` (i.e. Windows).
    """
    return Path(project_path) / ".sillon" / "daemon.port"

def get_tokenfile_path(project_path: str) -> Path:
    """Shared secret a client must present in its REGISTER frame."""
    return Path(project_path) / ".sillon" / "daemon.token"

def get_lockfile_path(project_path: str) -> Path:
    return Path(project_path) / ".sillon" / "daemon.lock"

def get_pidfile_path(project_path: str) -> Path:
    return Path(project_path) / ".sillon" / "daemon.pid"
