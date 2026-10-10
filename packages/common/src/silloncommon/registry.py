"""The machine-wide list of sillon projects.

Every project records itself here when its environment is created, so you can
find your projects later without remembering where you put them. This module
owns the file and nothing else: reading it, updating one entry, and repairing
it. Enrichment (run counts and the like) lives in `silloncore.projects`, which
can open project databases; this layer deliberately cannot.

The file is keyed by `project_id` for backward compatibility with registries
written by earlier versions, but an entry is *located* by its resolved project
path — so re-initialising a project updates its row instead of appending a new
one. Registries written before that change accumulated one row per init; call
`repair()` to collapse them.
"""

from pathlib import Path

import toml
from filelock import FileLock

from silloncommon.user_paths import user_config_dir

_LOCK_TIMEOUT = 10.0


def registry_path() -> Path:
    """Location of the registry file, per OS conventions."""
    return user_config_dir() / "registery.toml"


def _lock():
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(path.with_suffix(".lock")), timeout=_LOCK_TIMEOUT)


def _resolve(project_path) -> str:
    return str(Path(project_path).expanduser().resolve())


def _read_raw() -> dict:
    """The whole file as a dict. A missing or unreadable registry reads empty."""
    path = registry_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return toml.load(f)
    except (OSError, toml.TomlDecodeError):
        # A corrupt registry must not take down the run that is trying to
        # record itself; it is a convenience index, not primary data.
        return {}


def _write_raw(data: dict) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        toml.dump(data, f)


def _find_key_by_path(projects: dict, resolved_path: str):
    """The existing key for this project path, if it is already registered."""
    for key, entry in projects.items():
        recorded = entry.get("project_path")
        if recorded and _resolve(recorded) == resolved_path:
            return key
    return None


def _find_key_by_id(projects: dict, project_id: str):
    """The existing key for this project id, wherever it was last seen.

    `project_id` is minted once and lives in the project's own `config.toml`,
    so it travels with the directory. Finding a row by it is how a project
    that has been moved is recognised as the same project rather than
    registered again under its new path.
    """
    if not project_id:
        return None
    for key, entry in projects.items():
        if entry.get("project_id") == str(project_id):
            return key
    return None


def upsert(project_id, project_path, project_name, sillon_dir, storage_root) -> None:
    """Record (or update) one project. Safe to call concurrently.

    A project is matched by **path** first, then by **id**. The id match is
    what makes relocating a project just `mv`: the row is updated to point at
    where the project now is, instead of a second row appearing and the old
    one lingering as a phantom that `--prune` would have to clean up.
    """
    resolved = _resolve(project_path)
    with _lock():
        data = _read_raw()
        projects = data.setdefault("project", {})
        # Reuse the existing row for this path so repeated inits update in
        # place rather than appending a duplicate; failing that, the row for
        # this id, which is this project seen at a path it has since left.
        key = (
            _find_key_by_path(projects, resolved)
            or _find_key_by_id(projects, project_id)
            or str(project_id)
        )
        previous = projects.get(key, {})
        projects[key] = {
            # Keep a name that was recorded earlier if this init has none.
            "project_name": project_name or previous.get("project_name", ""),
            "project_id": previous.get("project_id", str(project_id)),
            "project_path": resolved,
            "project_sil": str(sillon_dir),
            "project_storage": str(storage_root),
        }
        _write_raw(data)


def register_if_moved(project_path) -> bool:
    """Bring the registry up to date when a project has been relocated.

    Called whenever a project is opened. A project carries its own identity in
    `.sillon/config.toml`, so `mv`-ing one is a perfectly reasonable thing to
    do — it just leaves this machine's registry pointing at where it used to
    be, which is what makes `sillon projects` show a phantom.

    Cheap in the normal case: one registry read, and no write unless the path
    actually changed. Never raises — a project must open even if the registry
    cannot be updated.

    Args:
        project_path (str | Path): The project root, as it is now.

    Returns:
        bool: True if a row was moved to this path.
    """
    try:
        from silloncommon import project_config

        resolved = _resolve(project_path)
        project_id = project_config.project_id(project_path)
        if not project_id:
            return False  # pre-2.0 project with no recorded identity

        projects = _read_raw().get("project", {}) or {}
        if _find_key_by_path(projects, resolved) is not None:
            return False  # already registered here; nothing to do

        key = _find_key_by_id(projects, project_id)
        if key is None:
            return False  # never registered on this machine

        entry = projects[key]
        upsert(
            project_id,
            project_path,
            entry.get("project_name") or project_config.project_name(project_path),
            project_config.sillon_dir(project_path),
            project_config.resolve_storage_root(project_path),
        )
        return True
    except Exception:
        return False


def entries() -> list:
    """Every registered project, as plain dicts with an `exists` flag.

    `exists` is False when the recorded path is gone — a deleted scratch
    project, or one written on another machine.
    """
    projects = _read_raw().get("project", {}) or {}
    out = []
    for entry in projects.values():
        path = entry.get("project_path", "")
        record = dict(entry)
        record["exists"] = bool(path) and Path(path).exists()
        out.append(record)
    out.sort(key=lambda e: (not e["exists"], (e.get("project_name") or "").lower(), e.get("project_path", "")))
    return out


def prune() -> list:
    """Drop entries whose project path no longer exists. Returns what was removed."""
    with _lock():
        data = _read_raw()
        projects = data.get("project", {}) or {}
        removed = [
            entry
            for entry in projects.values()
            if not (entry.get("project_path") and Path(entry["project_path"]).exists())
        ]
        data["project"] = {
            key: entry
            for key, entry in projects.items()
            if entry.get("project_path") and Path(entry["project_path"]).exists()
        }
        _write_raw(data)
    return removed


def repair() -> dict:
    """Collapse duplicate rows left by registries written before path-keying.

    Keeps the most informative row per path (one with a name beats one without)
    and rewrites paths in resolved form. Returns a small summary.
    """
    with _lock():
        data = _read_raw()
        projects = data.get("project", {}) or {}
        before = len(projects)

        best = {}
        for key, entry in projects.items():
            path = entry.get("project_path")
            if not path:
                continue
            resolved = _resolve(path)
            current = best.get(resolved)
            # Prefer an entry that actually carries a project name.
            if current is None or (
                not current[1].get("project_name") and entry.get("project_name")
            ):
                best[resolved] = (key, {**entry, "project_path": resolved})

        data["project"] = {key: entry for key, entry in best.values()}
        _write_raw(data)

    return {"before": before, "after": len(best), "removed": before - len(best)}
