from pathlib import Path

def get_socket_path(project_path: str) -> Path:
    return Path(project_path) / ".sillon" / "daemon.sock"

def get_lockfile_path(project_path: str) -> Path:
    return Path(project_path) / ".sillon" / "daemon.lock"

def get_pidfile_path(project_path: str) -> Path:
    return Path(project_path) / ".sillon" / "daemon.pid"
