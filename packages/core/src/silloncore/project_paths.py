"""Resolution of a sillon project's storage root and database engine.

A project keeps its data either directly under `.sillon/` or under a custom
storage root recorded in `.sillon/config.toml`. Both the CLI and sillonlab
need to find that data, so the logic lives here once.
"""

from pathlib import Path

import toml
from sqlmodel import create_engine

from silloncommon.database import get_engine


def resolve_storage_root(project_path) -> Path:
    """Returns the folder holding a project's `glob`, `artifact` and `figure` dirs.

    Reads the storage root from `.sillon/config.toml`, defaulting to the
    `.sillon` directory itself when no custom root is configured.

    Args:
        project_path (str | Path): The project root (folder containing `.sillon`).

    Returns:
        Path: The resolved storage root.
    """
    sillon_dir = Path(project_path).expanduser().resolve() / ".sillon"
    config_path = sillon_dir / "config.toml"
    if config_path.exists():
        config = toml.load(config_path)
        storage_root = config.get("storage", {}).get("storage_root")
        if storage_root:
            return Path(storage_root)
    return sillon_dir


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
            return create_engine("sqlite:///" + str(candidate))

    raise FileNotFoundError(f"No sillon database found for project {project_path}")
