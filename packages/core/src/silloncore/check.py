"""Does this project still say what it should?

Most of what sillon records is cross-referenced: a run row points at data on
disk, a lineage edge points at another run, a code version points at source
blobs, and the machine's registry points at the project. Each of those can
come apart — a pruned run, a half-finished copy, an import of a child without
its parent, a project moved while its data was on a disk that is not here.

None of it is fatal, and all of it is confusing when you meet it as a failed
read six months later. So it gets listed, with the fixes that are safe to
apply separated from the ones that are not.

Findings are data, as everywhere else in the engine; the CLI and sillonlab
render the same ones. Nothing here touches a run row: the worst case is that
`check` is wrong about something, and it must not be able to delete your work
on that basis.
"""

from pathlib import Path

from silloncommon import project_config, registry
from silloncommon.database import select_run_index, select_uuids
from silloncommon.source_store import sources_dir

from silloncore.bundle import DATA_GROUPS

__all__ = ["check_project", "repair_project", "SEVERITIES"]

# How much a finding deserves to be looked at. `broken` means something that
# is already failing; `stale` means something that will mislead; `tidy` means
# wasted space and nothing more.
SEVERITIES = ("broken", "stale", "tidy")


def _finding(kind, severity, message, detail=None, repairable=False) -> dict:
    return {
        "kind": kind,
        "severity": severity,
        "message": message,
        "detail": detail or {},
        "repairable": repairable,
    }


def check_project(engine, storage_root, project_path) -> dict:
    """Every cross-reference in a project that no longer holds.

    `engine` may be None, for a project whose database cannot be opened at
    all — which is exactly when you would reach for this. The checks that need
    the database are then skipped and that fact is itself the first finding.

    Args:
        engine (Engine | None): The project's database engine, or None if it
            could not be opened.
        storage_root (str | Path): The project's storage root.
        project_path (str | Path): The project root.

    Returns:
        dict: `{"project", "run_count", "findings", "counts", "healthy"}`,
            where each finding is `{"kind", "severity", "message", "detail",
            "repairable"}`.
    """
    storage_root = Path(storage_root)
    project_path = Path(project_path).expanduser().resolve()

    findings = []
    findings.extend(_check_storage_root(project_path))

    if engine is None:
        index = []
        findings.append(
            _finding(
                "database_unreadable",
                "broken",
                "the project's database could not be opened, so its runs "
                "could not be checked",
                {},
            )
        )
    else:
        index = select_run_index(engine)
        findings.extend(_check_duplicate_identities(index))
        findings.extend(_check_run_data(index, storage_root))
        findings.extend(_check_orphan_data(index, storage_root))
        findings.extend(_check_lineage(index, engine))
        findings.extend(_check_sources(index, storage_root))

    findings.extend(_check_registry(project_path))

    order = {name: position for position, name in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (order.get(f["severity"], 9), f["kind"]))

    counts = {name: 0 for name in SEVERITIES}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1

    return {
        "project": str(project_path),
        "run_count": len(index),
        "findings": findings,
        "counts": counts,
        "healthy": not findings,
    }


# ==========================================
#                 THE CHECKS
# ==========================================


def _check_storage_root(project_path) -> list:
    """A recorded storage root that is not there any more."""
    recorded = (project_config.read_config(project_path).get("storage") or {}).get(
        "storage_root"
    )
    if not recorded:
        return []
    root = Path(recorded).expanduser()
    if not root.is_absolute():
        root = project_path / root
    if root.exists():
        return []
    return [
        _finding(
            "storage_root_missing",
            "broken",
            f"the recorded storage root is not there: {recorded}",
            {"recorded": recorded},
        )
    ]


def _check_duplicate_identities(index) -> list:
    """Two rows claiming to be the same run, or the same name.

    A duplicate uuid is invisible to anything that takes `.first()` while the
    index and query paths still count it. A duplicate name makes
    `sillon show <name>` ambiguous — the importer suffixes precisely to keep
    that from happening, so one here means a database that predates it or was
    edited by hand.
    """
    findings = []
    for field, kind, severity, what in (
        ("uuid", "duplicate_uuid", "broken", "runs share a uuid"),
        ("name", "duplicate_name", "stale", "runs share a name"),
    ):
        seen = {}
        for entry in index:
            seen.setdefault(entry[field], []).append(entry["name"])
        for value, names in seen.items():
            if len(names) > 1:
                findings.append(
                    _finding(
                        kind,
                        severity,
                        f"{len(names)} {what}: {value}",
                        {field: value, "runs": names},
                    )
                )
    return findings


def _check_run_data(index, storage_root) -> list:
    """Runs whose data a row claims and disk does not have.

    Expected after `prune` or an `import --no-data`, and worth saying either
    way: in `sillon list` a stub is indistinguishable from a complete run
    until a read fails.
    """
    findings = []
    for entry in index:
        uuid = entry["uuid"]
        wants_glob = bool(entry.get("result_names")) or bool(entry.get("analyses"))
        missing = []
        if wants_glob and not (storage_root / "glob" / uuid / "glob.hdf5").is_file():
            missing.append("glob")
        if entry.get("artifacts") and not (storage_root / "artifact" / uuid).is_dir():
            missing.append("artifact")
        if entry.get("figures") and not (storage_root / "figure" / uuid).is_dir():
            missing.append("figure")
        if missing:
            findings.append(
                _finding(
                    "run_data_missing",
                    "stale",
                    f"{entry['name']} has no {', '.join(missing)} data on disk",
                    {"run": entry["name"], "uuid": uuid, "groups": missing},
                )
            )
    return findings


def _check_orphan_data(index, storage_root) -> list:
    """Data directories with no run row behind them.

    Wasted space, and a sign a delete did not finish. Safe to remove, because
    nothing can reach them: every reader starts from a row.
    """
    known = {entry["uuid"] for entry in index}
    findings = []
    for group in DATA_GROUPS:
        folder = storage_root / group
        if not folder.is_dir():
            continue
        for item in sorted(folder.iterdir()):
            if item.is_dir() and item.name not in known:
                findings.append(
                    _finding(
                        "orphan_data",
                        "tidy",
                        f"{group}/{item.name} belongs to no run",
                        {"group": group, "uuid": item.name, "path": str(item)},
                        repairable=True,
                    )
                )
    return findings


def _check_lineage(index, engine) -> list:
    """Parent edges pointing at runs that are not here.

    Kept deliberately — the edge is still a true statement about where a run
    came from — but unwalkable, so saying so beats a LookupError later. The
    usual cause is importing a child without its parent.
    """
    known = select_uuids(engine)
    findings = []
    for entry in index:
        for edge in entry.get("parents") or []:
            parent_uuid = edge.get("uuid")
            if parent_uuid and parent_uuid not in known:
                findings.append(
                    _finding(
                        "parent_missing",
                        "stale",
                        f"{entry['name']}'s parent "
                        f"{edge.get('name') or parent_uuid[:8]} is not in this project",
                        {
                            "run": entry["name"],
                            "parent_uuid": parent_uuid,
                            "parent_name": edge.get("name") or "",
                        },
                    )
                )
    return findings


def _check_sources(index, storage_root) -> list:
    """The code behind each run: blobs referenced but absent, and the reverse.

    `prune` has never cleaned `sources/`, so orphans accumulate. They are
    small (text, deduplicated by content) and removing them is safe only
    because every reference is a hash that no longer appears anywhere.
    """
    referenced = set()
    for entry in index:
        version = (entry.get("meta_data") or {}).get("sillon.code.version") or {}
        for info in (version.get("files") or {}).values():
            digest = (info or {}).get("source_hash")
            if digest:
                referenced.add(digest)

    folder = sources_dir(storage_root)
    present = set()
    if folder.is_dir():
        present = {
            blob.name
            for blob in folder.iterdir()
            if blob.is_file() and not blob.name.startswith(".")
        }

    findings = []
    missing = referenced - present
    if missing:
        findings.append(
            _finding(
                "source_missing",
                "stale",
                f"{len(missing)} source file(s) a code version refers to are not stored",
                {"hashes": sorted(missing)},
            )
        )
    orphans = present - referenced
    if orphans:
        findings.append(
            _finding(
                "orphan_source",
                "tidy",
                f"{len(orphans)} stored source file(s) no run refers to",
                {"hashes": sorted(orphans)},
                repairable=True,
            )
        )
    return findings


def _check_registry(project_path) -> list:
    """Whether this machine's listing agrees with the project itself."""
    project_id = project_config.project_id(project_path)
    if not project_id:
        return [
            _finding(
                "no_project_id",
                "stale",
                "the project has no recorded id, so it cannot be recognised "
                "after being moved",
                {},
            )
        ]

    try:
        rows = registry.entries()
    except Exception:
        return []

    here = [r for r in rows if r.get("project_path") == str(project_path)]
    if here:
        return []
    elsewhere = [r for r in rows if r.get("project_id") == project_id]
    if elsewhere:
        return [
            _finding(
                "registry_stale",
                "stale",
                f"the registry lists this project at {elsewhere[0]['project_path']}",
                {"recorded": elsewhere[0]["project_path"]},
                repairable=True,
            )
        ]
    return [
        _finding(
            "registry_missing",
            "stale",
            "this project is not in this machine's listing",
            {},
            repairable=True,
        )
    ]


# ==========================================
#                 REPAIR
# ==========================================


def repair_project(engine, storage_root, project_path) -> dict:
    """Applies the fixes that cannot lose anything.

    Only the findings marked `repairable`: re-registering the project, and
    deleting data and source blobs that no row refers to. Nothing here touches
    a run row, a parameter or a result — the point of a repair you can run
    without reading the report first is that being wrong about a finding costs
    you nothing.

    Everything else is reported and left alone, because the fix is a judgement
    call: a run whose data is gone might want deleting or might want re-running.

    Args:
        engine (Engine): The project's database engine.
        storage_root (str | Path): The project's storage root.
        project_path (str | Path): The project root.

    Returns:
        dict: The check result, plus `{"repaired", "freed_bytes", "remaining"}`.
    """
    import shutil

    result = check_project(engine, storage_root, project_path)
    repaired, freed = [], 0

    for finding in result["findings"]:
        if not finding["repairable"]:
            continue

        if finding["kind"] == "orphan_data":
            target = Path(finding["detail"]["path"])
            freed += _directory_size(target)
            shutil.rmtree(target, ignore_errors=True)
            repaired.append(finding)

        elif finding["kind"] == "orphan_source":
            folder = sources_dir(storage_root)
            for digest in finding["detail"]["hashes"]:
                blob = folder / digest
                try:
                    freed += blob.stat().st_size
                    blob.unlink()
                except OSError:
                    continue
            repaired.append(finding)

        elif finding["kind"] in ("registry_stale", "registry_missing"):
            project_path = Path(project_path).expanduser().resolve()
            try:
                registry.upsert(
                    project_config.project_id(project_path),
                    project_path,
                    project_config.project_name(project_path),
                    project_config.sillon_dir(project_path),
                    storage_root,
                )
                repaired.append(finding)
            except Exception:
                pass

    done = {id(f) for f in repaired}
    return {
        **result,
        "repaired": repaired,
        "freed_bytes": freed,
        "remaining": [f for f in result["findings"] if id(f) not in done],
    }


def _directory_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
    except OSError:
        pass
    return total
