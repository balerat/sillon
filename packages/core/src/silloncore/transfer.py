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

from pathlib import Path

from sqlmodel import Session

from silloncommon.database import (
    insert_imported_run,
    resolve_available_name,
    select_names,
    select_uuids,
)

from silloncore.bundle import BundleError, BundleSource

__all__ = ["plan_import", "import_source", "open_source"]


def open_source(path):
    """A bundle file or a project directory, as something an import can read.

    Raises:
        BundleError: If the path is neither.
    """
    path = Path(path).expanduser()
    if path.is_file():
        return BundleSource(path)
    raise BundleError(
        f"{path} is not a sillon bundle. "
        "Importing a project directory is not supported yet."
    )


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
    suffix = _suffix_for(describe.get("hostname") or describe.get("project_name"))

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
