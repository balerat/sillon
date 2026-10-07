"""Resolution of a sillon project's storage root and database engine.

A project keeps its data either directly under `.sillon/` or under a custom
storage root recorded in `.sillon/config.toml`. Both the CLI and sillonlab
need to find that data, so the logic lives here once.
"""

from pathlib import Path

from sqlmodel import create_engine

from silloncommon import project_config
from silloncommon.database import get_engine, migrate_schema, sqlite_url

# The config is parsed in exactly one place, shared with the client and the
# daemon, because this module and the daemon used to disagree about it.
resolve_storage_root = project_config.resolve_storage_root


def resolve_engine(project_path):
    """Connects to a project's SQLite database, wherever it was created.

    Handles both the default layout (`.sillon/database.sql`) and layouts
    produced with a custom storage root.

    Args:
        project_path (str | Path): The project root (folder containing `.sillon`).

    Raises:
        FileNotFoundError: If no database can be located for the project.

    Returns:
        Engine: A SQLAlchemy engine connected to the project database.
    """
    project_path = Path(project_path).expanduser().resolve()
    sillon_dir = project_path / ".sillon"

    if (sillon_dir / "database.sql").exists():
        return get_engine(project_path)

    storage_root = resolve_storage_root(project_path)
    for candidate in (
        storage_root / "database.sql",
        storage_root / ".sillon" / "database.sql",
    ):
        if candidate.exists():
            return migrate_schema(create_engine(sqlite_url(candidate)))

    raise FileNotFoundError(f"No sillon database found for project {project_path}")


def resolve_project_name(project_path) -> str:
    """The project's own name, as recorded in its config.

    Comes from `.sillon/config.toml` so it survives being copied or moved;
    falls back to the machine-wide registry for projects created before the
    name was stored there. Empty string when nothing knows it.

    Args:
        project_path (str | Path): The project root.

    Returns:
        str: The project name, or "".
    """
    name = project_config.project_name(project_path)
    if name:
        return name

    try:
        from silloncommon import registry

        resolved = str(Path(project_path).expanduser().resolve())
        for entry in registry.entries():
            if entry.get("project_path") == resolved and entry.get("project_name"):
                return entry["project_name"]
    except Exception:
        pass
    return ""
