"""Machine-wide project listing — the engine behind `sillon projects`.

`silloncommon.registry` owns the registry file but cannot open project
databases (it sits below silloncore). This module joins the two: registry
entries plus a run count and last-activity date read from each project.

Returns plain data, like the rest of the engine layer, so the CLI and sillonlab
render the same records.
"""

from pathlib import Path

from silloncommon import registry
from silloncommon.database import select_run_index

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

    dates = [entry["date"] for entry in index if entry.get("date")]
    return {
        "run_count": len(index),
        "last_activity": max(dates) if dates else None,
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
