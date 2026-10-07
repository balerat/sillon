"""Bringing runs into a project from somewhere else.

The rule is **union, never overwrite**. A run already here is left exactly as
it is; a run that is not is added. Nothing an import does can lose work, which
is what makes it safe to repeat — and repeating is the normal case, since
re-importing a bundle you already read is how you find out whether there is
anything new in it.

Identity is the run uuid, which has been a client-side uuid4 since the
beginning and is therefore already globally unique. Names are not identity:
two machines will both produce a `deg3`, and `next_available_name` has only
ever deduplicated against one database. So an incoming name that is taken gets
suffixed with where it came from, and the local run keeps its name.

That suffixing is load-bearing, not cosmetic. It is what keeps names unique
*within* a project, which is what lets `sillon show deg3` and `query` go on
returning one run. Lineage does not depend on it — edges are followed by uuid
(see `Run.parents`) — precisely so that renaming on the way in cannot bend a
parent edge onto the wrong run.
"""

import shutil
from collections import Counter
from pathlib import Path

from sqlmodel import Session

from silloncommon import project_config
from silloncommon.database import (
    insert_imported_run,
    resolve_available_name,
    schema_version,
    select_names,
    select_run_identities,
    select_run_snapshot,
    select_uuids,
)
from silloncommon.source_store import sources_dir

from silloncore.bundle import DATA_GROUPS, BundleError, BundleSource

__all__ = [
    "plan_import",
    "import_source",
    "open_source",
    "ProjectSource",
    "find_projects",
]


def open_source(path):
    """A bundle file or a project directory, as something an import can read.

    Crossing a machine boundary needs a bundle; on one machine the other
    project is right there, so there is no reason to make you pack it first.

    Raises:
        BundleError: If the path is neither.
    """
    path = Path(path).expanduser()
    if path.is_file():
        return BundleSource(path)
    if path.is_dir():
        if (path / ".sillon").is_dir():
            return ProjectSource(path)
        raise BundleError(
            f"{path} is a directory but not a sillon project (no .sillon/). "
            "Use --scan to search it for projects."
        )
    raise BundleError(f"No such bundle or project: {path}")


def find_projects(root, skip=()) -> list:
    """Every sillon project under a directory tree.

    The answer to a history of projects made wherever the script happened to
    be -- including the layouts where a project's data ended up a level above
    it. Does not descend into a project it has already found, so a `.sillon`
    inside a project's own data is not mistaken for a second project.

    Args:
        root (str | Path): The directory to search.
        skip (Iterable[str | Path]): Project roots to leave out, normally the
            destination itself.

    Returns:
        list[Path]: Project roots, shallowest first.
    """
    root = Path(root).expanduser().resolve()
    skipped = {Path(p).expanduser().resolve() for p in skip}

    found = []
    if (root / ".sillon").is_dir() and root not in skipped:
        found.append(root)

    for sillon_dir in sorted(root.rglob(".sillon")):
        if not sillon_dir.is_dir():
            continue
        project = sillon_dir.parent
        if project in skipped or project == root:
            continue
        # Already covered by a project above it: `.sillon/glob/...` can hold
        # anything, and a nested project is not a thing sillon creates.
        if any(project != other and other in project.parents for other in found):
            continue
        found.append(project)

    return found


class ProjectSource:
    """Another project on this machine, as a source an import can read.

    The same interface as `BundleSource`, so the importer does not know or care
    which it is given. Reading goes through the ordinary engine and snapshot
    functions rather than anything bespoke -- a foreign project is just a
    project you are not standing in.
    """

    def __init__(self, path):
        from silloncore.project_paths import resolve_engine, resolve_storage_root

        self.path = Path(path).expanduser().resolve()
        if not (self.path / ".sillon").is_dir():
            raise BundleError(f"{self.path} is not a sillon project (no .sillon/).")
        try:
            self.engine = resolve_engine(self.path)
        except FileNotFoundError as exc:
            raise BundleError(f"{self.path} has no sillon database.") from exc
        self.storage_root = resolve_storage_root(self.path)
        self._identities = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        # The engine's connections are pooled; dispose so a source project can
        # be moved or deleted right after an import without a lingering handle.
        self.engine.dispose()
        return False

    def _ids(self) -> list:
        if self._identities is None:
            self._identities = select_run_identities(self.engine)
        return self._identities

    def describe(self) -> dict:
        # The hostname a colliding name gets tagged with. A project's runs can
        # come from several machines once it has been merged into before, so
        # the most common one is the honest answer rather than the first.
        hosts = Counter(
            entry.get("hostname")
            for entry in self._run_rows()
            if entry.get("hostname")
        )
        name = project_config.project_name(self.path) or self.path.name
        return {
            "kind": "project",
            "label": str(self.path),
            # For a project on this machine the hostname is *our* hostname, so
            # tagging a collision with it says nothing. The project's name is
            # the difference that matters.
            "origin_label": name,
            "project_id": project_config.project_id(self.path),
            "project_name": name,
            "hostname": hosts.most_common(1)[0][0] if hosts else "",
            "created": None,
            "sillon_version": None,
            "schema_version": schema_version(self.engine),
            "has_data": (Path(self.storage_root) / "glob").is_dir(),
            "run_count": len(self._ids()),
        }

    def _run_rows(self) -> list:
        from silloncommon.database import select_run_index

        if not hasattr(self, "_rows"):
            self._rows = select_run_index(self.engine)
        return self._rows

    def run_uuids(self) -> list:
        return [entry["uuid"] for entry in self._ids()]

    def read_run(self, uuid: str) -> dict:
        run, artifacts, figures, analyses = select_run_snapshot(self.engine, uuid)
        if run is None:
            raise BundleError(f"{self.path} is missing run {uuid}.")
        return {
            "run": run,
            "artifacts": artifacts,
            "figures": figures,
            "analyses": analyses,
        }

    def copy_run_data(self, uuid: str, storage_root) -> int:
        """Copy a run's data trees across. Returns how many files were written."""
        storage_root = Path(storage_root)
        written = 0
        for group in DATA_GROUPS:
            origin = Path(self.storage_root) / group / str(uuid)
            if not origin.is_dir():
                continue
            target = storage_root / group / str(uuid)
            target.mkdir(parents=True, exist_ok=True)
            for item in sorted(origin.rglob("*")):
                if not item.is_file():
                    continue
                destination = target / item.relative_to(origin)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)
                written += 1
        return written

    def copy_sources(self, storage_root) -> int:
        """Union the source stores. Returns how many blobs were new."""
        origin = sources_dir(self.storage_root)
        if not origin.is_dir():
            return 0
        target_dir = sources_dir(storage_root)
        written = 0
        for blob in sorted(origin.iterdir()):
            if not blob.is_file() or blob.name.startswith("."):
                continue
            target = target_dir / blob.name
            if target.exists():
                continue  # content-addressed: it cannot differ
            target_dir.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{blob.name}.import.tmp")
            shutil.copy2(blob, tmp)
            tmp.replace(target)
            written += 1
        return written


def _suffix_for(source_label: str) -> str:
    """The tag appended to a colliding name — where the run came from."""
    cleaned = "".join(ch for ch in str(source_label or "") if ch.isalnum() or ch in "._-")
    return cleaned or "imported"


def plan_import(engine, source, with_data: bool = True) -> dict:
    """What an import would do, without doing any of it.

    Resolving names here rather than inside the write loop means the plan a
    `--dry-run` prints is the plan that gets carried out, not an estimate of
    it.

    Args:
        engine (Engine): The destination project's database engine.
        source: An opened source (see `open_source`).
        with_data (bool): Whether the heavy data would be copied.

    Returns:
        dict: `{"source", "new", "already_here", "renamed", "stubs",
            "parents_missing"}`, where `new` is a list of
            `{"uuid", "name", "original_name"}` in the order they would be
            written.
    """
    describe = source.describe()
    existing_uuids = select_uuids(engine)
    # Fetched once. Names claimed earlier in this same import count as taken
    # too, or two incoming runs called `deg3` would both land as `deg3~laptop`.
    taken = select_names(engine)
    suffix = _suffix_for(
        describe.get("origin_label")
        or describe.get("hostname")
        or describe.get("project_name")
    )

    new, already_here, renamed = [], [], []
    incoming_uuids = set()

    for uuid in source.run_uuids():
        incoming_uuids.add(uuid)
        record = source.read_run(uuid)
        original = (record.get("run") or {}).get("name") or ""

        if uuid in existing_uuids:
            already_here.append({"uuid": uuid, "name": original})
            continue

        if original in taken:
            # A bare increment would make it `deg3_2`, which says nothing
            # about where it came from. Tag it with the origin instead, and
            # fall back to the increment only if that is taken as well.
            name = resolve_available_name(f"{original}~{suffix}", taken)
            renamed.append({"uuid": uuid, "from": original, "to": name})
        else:
            name = original
        taken.add(name)
        new.append({"uuid": uuid, "name": name, "original_name": original})

    # Lineage edges whose other end is in neither place. The edge is still a
    # true statement about where the run came from, so it is kept -- but it
    # cannot be walked, and saying so now beats a LookupError later.
    known = existing_uuids | incoming_uuids
    parents_missing = []
    for entry in new:
        record = source.read_run(entry["uuid"])
        for edge in (record.get("run") or {}).get("parents") or []:
            parent_uuid = edge.get("uuid")
            if parent_uuid and parent_uuid not in known:
                parents_missing.append(
                    {
                        "run": entry["name"],
                        "parent_uuid": parent_uuid,
                        "parent_name": edge.get("name") or "",
                    }
                )

    return {
        "source": describe,
        "new": new,
        "already_here": already_here,
        "renamed": renamed,
        # A run whose data is deliberately not coming: either the bundle was
        # written with --no-data, or this import was asked not to copy it.
        "stubs": list(new) if not (with_data and describe.get("has_data")) else [],
        "parents_missing": parents_missing,
    }


def import_source(engine, storage_root, source, with_data: bool = True) -> dict:
    """Adds every run the source has and the project does not.

    One transaction for the rows: an import either lands or does not, and a
    half-imported project is never a state anyone has to reason about. The
    data copy happens first, per run, because a row pointing at data that is
    not there is a worse failure than data on disk that no row claims --
    `check` finds the second and nothing finds the first.

    Args:
        engine (Engine): The destination project's database engine.
        storage_root (str | Path): The destination project's storage root.
        source: An opened source (see `open_source`).
        with_data (bool): Copy the heavy data. False imports the rows only.

    Returns:
        dict: The plan, plus `{"imported", "files_copied", "sources_copied"}`.
    """
    storage_root = Path(storage_root)
    plan = plan_import(engine, source, with_data=with_data)

    copy_data = with_data and plan["source"].get("has_data")
    files_copied = 0
    sources_copied = 0

    if plan["new"]:
        for entry in plan["new"]:
            if copy_data:
                files_copied += source.copy_run_data(entry["uuid"], storage_root)

        if copy_data:
            sources_copied = source.copy_sources(storage_root)

        with Session(engine) as session:
            for entry in plan["new"]:
                record = source.read_run(entry["uuid"])
                insert_imported_run(record, session, name=entry["name"])
            session.commit()

    return {
        **plan,
        "imported": len(plan["new"]),
        "files_copied": files_copied,
        "sources_copied": sources_copied,
    }
