"""`.sillon/config.toml` — the one place that reads and writes it.

Three modules used to parse this file independently: the daemon's two
environment handlers and `silloncore.project_paths`. They disagreed. The
daemon honoured `[storage].storage_root`, the readers had the same lines
commented out and always assumed `.sillon`, so moving a project left readers
working while the next run the daemon logged wrote its data to the old path.

It lives in `silloncommon` because all three sides need the same answer: the
client (`sillonpy`) writes staged arrays and source text, the daemon writes
runs, and the interfaces (`silloncli`, `sillonlab`) read them.

The storage root is stored **relative to the project root whenever it is
inside it**, so copying or moving a project does not invalidate it. An
external root — heavy data on a different disk — is necessarily absolute and
does not travel; `resolve_storage_root` falls back rather than pointing at a
path that is not there, and `sillon check` reports it.
"""

from pathlib import Path

import toml

__all__ = [
    "SILLON_DIR",
    "config_path",
    "find_project_root",
    "read_config",
    "write_config",
    "resolve_storage_root",
    "store_storage_root",
    "project_id",
    "project_name",
]

SILLON_DIR = ".sillon"


def sillon_dir(project_path) -> Path:
    """The `.sillon` directory of a project."""
    return Path(project_path).expanduser().resolve() / SILLON_DIR


def config_path(project_path) -> Path:
    """Where a project's config lives."""
    return sillon_dir(project_path) / "config.toml"


def read_config(project_path) -> dict:
    """The project's config, or `{}` when there is none or it is unreadable.

    A corrupt config must not stop a run from being logged, so this never
    raises — the callers all have a sensible default.
    """
    try:
        return toml.load(config_path(project_path))
    except (OSError, toml.TomlDecodeError):
        return {}


def write_config(project_path, config: dict) -> None:
    """Replace a project's config."""
    target = config_path(project_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        toml.dump(config, handle)


def store_storage_root(project_path, storage_root) -> str:
    """How a storage root should be written into the config.

    Relative to the project root when it is inside it (so the project can be
    moved or copied), absolute otherwise. POSIX separators, so a config
    written on Windows still reads on macOS.
    """
    project_path = Path(project_path).expanduser().resolve()
    storage_root = Path(storage_root).expanduser().resolve()
    try:
        return storage_root.relative_to(project_path).as_posix()
    except ValueError:
        return str(storage_root)


def resolve_storage_root(project_path) -> Path:
    """The folder holding a project's `glob`, `artifact` and `figure` dirs.

    Reads `[storage].storage_root`, resolving a relative value against the
    project root. Defaults to `.sillon`.

    A recorded root that no longer exists is ignored in favour of `.sillon` —
    that is a project which was moved while its data was on another disk, and
    answering with the old path would only produce confusing errors further
    in. `sillon check` is where that gets reported.

    Args:
        project_path (str | Path): The project root (the folder with `.sillon`).

    Returns:
        Path: The resolved storage root.
    """
    project_path = Path(project_path).expanduser().resolve()
    default = project_path / SILLON_DIR

    recorded = (read_config(project_path).get("storage") or {}).get("storage_root")
    if not recorded:
        return default

    root = Path(recorded).expanduser()
    if not root.is_absolute():
        root = project_path / root
    root = root.resolve()

    if root == default or root.exists():
        return root
    return default


def project_id(project_path) -> str:
    """The project's own id, stable across copies. `""` when unknown."""
    return (read_config(project_path).get("Environment") or {}).get("project_id") or ""


def project_name(project_path) -> str:
    """The project's own name, as recorded in its config. `""` when unset."""
    return (read_config(project_path).get("Environment") or {}).get("project_name") or ""


def find_project_root(start=None):
    """The project a path is inside, searching upward. None if there is none.

    Like git: standing in `analysis/figures/` should work, because that is
    where you are when you want to look something up. Stops at the filesystem
    root, and at a mount point only in the sense that it will keep walking --
    a project above a mount is still your project.

    Args:
        start (str | Path, optional): Where to start. Defaults to the current
            directory.

    Returns:
        Path | None: The project root, or None if no ancestor has `.sillon/`.
    """
    current = Path(start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / SILLON_DIR).is_dir():
            return candidate
    return None
