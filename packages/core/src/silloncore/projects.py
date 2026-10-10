"""Machine-wide project listing — the engine behind `sillon projects`.

`silloncommon.registry` owns the registry file but cannot open project
databases (it sits below silloncore). This module joins the two: registry
entries plus a run count and last-activity date read from each project.

Returns plain data, like the rest of the engine layer, so the CLI and sillonlab
render the same records.
"""

import os
import stat
import uuid
from pathlib import Path

from silloncommon import project_config, registry
from silloncommon.database import create_default_engine_root, select_run_index

from silloncore.project_paths import resolve_engine


def _project_stats(project_path) -> dict:
    """Run count and latest run date for one project, best-effort.

    A project can be registered but unreadable — deleted, on an unmounted
    volume, or written by a newer sillon. That is reported, not raised: one bad
    project must not break the listing of all the others.
    """
    try:
        engine = resolve_engine(Path(project_path))
        index = select_run_index(engine)
    except Exception:
        return {"run_count": None, "last_activity": None, "readable": False}

    # Keyed on `when` (timezone-correct) but reported as `date`, which is the
    # string the projects table displays.
    dated = [(entry.get("when") or "", entry["date"]) for entry in index if entry.get("date")]
    return {
        "run_count": len(index),
        "last_activity": max(dated)[1] if dated else None,
        "readable": True,
    }


def get_projects(include_missing: bool = True, with_stats: bool = True) -> list:
    """Every project registered on this machine.

    Args:
        include_missing (bool): Keep entries whose directory is gone. They are
            flagged `exists=False` rather than hidden, so a project on an
            unmounted drive is visible instead of silently absent.
        with_stats (bool): Open each project database for a run count and last
            activity date. Set False for a fast, filesystem-only listing.

    Returns:
        list[dict]: `project_name`, `project_path`, `project_storage`, `exists`,
            and when `with_stats`, `run_count`, `last_activity`, `readable`.
    """
    records = []
    for entry in registry.entries():
        if not entry["exists"] and not include_missing:
            continue

        record = {
            "project_name": entry.get("project_name") or "",
            "project_path": entry.get("project_path", ""),
            "project_storage": entry.get("project_storage", ""),
            "project_id": entry.get("project_id", ""),
            "exists": entry["exists"],
        }
        if with_stats and entry["exists"]:
            record.update(_project_stats(entry["project_path"]))
        else:
            record.update({"run_count": None, "last_activity": None, "readable": False})
        records.append(record)

    return records


def find_project(name_or_path: str):
    """Resolve a project by name or path. Returns the record, or None.

    Name matching is case-insensitive and falls back to a unique prefix, so
    `sillon projects` output can be used directly.
    """
    records = get_projects(with_stats=False)
    needle = name_or_path.strip()

    resolved = str(Path(needle).expanduser().resolve())
    for record in records:
        if record["project_path"] == resolved:
            return record

    lowered = needle.lower()
    exact = [r for r in records if r["project_name"].lower() == lowered]
    if len(exact) == 1:
        return exact[0]

    prefix = [r for r in records if r["project_name"].lower().startswith(lowered)]
    if len(prefix) == 1:
        return prefix[0]
    return None


def prune_projects() -> dict:
    """Forget registered projects whose directory no longer exists."""
    removed = registry.prune()
    return {"removed_count": len(removed), "removed": removed}


def repair_registry() -> dict:
    """Collapse duplicate rows left by older sillon versions."""
    return registry.repair()


def create_project(
    project_path, project_name: str = None, storage_root=None, exist_ok: bool = True
) -> dict:
    """Creates (or opens) a project's `.sillon` directory, config and database.

    The one implementation of "make this directory a project", shared by
    `sillon init` and the daemon — which has always done it as a side effect of
    the first run being logged, and must keep doing so, because zero-config
    logging is the point of sillon.

    Idempotent: pointed at a project that already exists it opens it, learns
    the name if one is supplied and none was recorded, and heals a storage root
    that no longer resolves.

    Args:
        project_path (str | Path): The directory to make a project.
        project_name (str, optional): The project's name. Only written when
            there is not one already, so opening never renames a project.
        storage_root (str | Path, optional): Where the heavy data should live.
            Only honoured when the project is being created; an existing
            project keeps the root it has.
        exist_ok (bool): When False, raise if the directory is already a
            project.

    Raises:
        FileExistsError: If `exist_ok` is False and `.sillon/` is already there.

    Returns:
        dict: `{"path", "project_id", "project_name", "storage_root",
            "created"}`.
    """
    project_path = Path(project_path).expanduser().resolve()
    sillon_dir = project_path / project_config.SILLON_DIR
    existed = sillon_dir.is_dir() and project_config.config_path(project_path).is_file()
    if existed and not exist_ok:
        raise FileExistsError(f"{project_path} is already a sillon project.")

    sillon_dir.mkdir(parents=True, exist_ok=True)
    config = project_config.read_config(project_path) if existed else {}
    environment = config.setdefault("Environment", {})

    project_id = environment.get("project_id") or str(uuid.uuid4())
    environment["project_id"] = project_id
    # A name is learned, never overwritten: opening a project must not rename
    # it just because a caller passed something different.
    environment["project_name"] = environment.get("project_name") or (project_name or "")

    if existed:
        # Honour (and normalise) the root it already has, which also rewrites
        # a stale absolute one -- a project moved while its data was elsewhere.
        resolved_root = project_config.resolve_storage_root(project_path)
    elif storage_root:
        resolved_root = Path(storage_root).expanduser().resolve()
    else:
        resolved_root = sillon_dir
    config.setdefault("storage", {})["storage_root"] = project_config.store_storage_root(
        project_path, resolved_root
    )
    project_config.write_config(project_path, config)

    resolved_root.mkdir(parents=True, exist_ok=True)
    # Creates database.sql if it is not there, and migrates it if it is.
    create_default_engine_root(resolved_root).dispose()
    _grant_group_access(sillon_dir, resolved_root / "database.sql")

    try:
        registry.upsert(
            project_id,
            project_path,
            environment["project_name"],
            sillon_dir,
            resolved_root,
        )
    except Exception:
        pass  # an unwritable registry must not stop a project from existing

    return {
        "path": project_path,
        "project_id": project_id,
        "project_name": environment["project_name"],
        "storage_root": resolved_root,
        "created": not existed,
    }


def _grant_group_access(sillon_dir: Path, db_path: Path) -> None:
    """Make the project group-writable, for a shared machine.

    POSIX only: Windows' `os.chmod` honours nothing but the read-only bit, so
    every flag below would be silently discarded there.
    """
    if os.name != "posix":
        return
    for target in (sillon_dir, db_path):
        try:
            mode = os.stat(target).st_mode
            os.chmod(target, mode | stat.S_IWUSR | stat.S_IWGRP | (
                stat.S_IXUSR | stat.S_IXGRP if target.is_dir() else 0
            ))
        except OSError:
            pass
