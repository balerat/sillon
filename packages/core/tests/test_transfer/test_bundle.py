"""The bundle format, and the first code in sillon that reads data back in.

`report` has always been able to write a zip, but it is lossy on purpose and
nothing ever read one. These tests are about the other thing: a file that
reconstructs a run somewhere else, byte for byte, and an import whose rule is
union-never-overwrite — so running it twice is a no-op and running it can
never lose local work.

The heavy fidelity checks live in the real-daemon suite
(`packages/pyapi/tests/test_portability/test_round_trip.py`), which logs runs
through the actual client. These cover the format, the plan and the edge cases
that are tedious to produce with a real run.
"""

import json
import zipfile
from pathlib import Path

import h5py
import numpy as np
import pytest
from sqlmodel import Session, select

from silloncommon.database import (
    ArtifactTable,
    FigureTable,
    SimulationTable,
    make_engine,
    migrate_schema,
    select_run_index,
)
from silloncore.bundle import (
    BUNDLE_FORMAT,
    MANIFEST_NAME,
    BundleError,
    BundleSource,
    default_bundle_name,
    read_manifest,
)
from silloncore.engine import export_bundle, import_from, inspect_bundle

RUN_A = "aaaaaaaa-0000-0000-0000-00000000000a"
RUN_B = "bbbbbbbb-0000-0000-0000-00000000000b"
ARTIFACT_ID = "11111111-0000-0000-0000-000000000001"
FIGURE_ID = "22222222-0000-0000-0000-000000000002"
SOURCE_HASH = "deadbeef" * 8


def _row(uuid, name, degree, parents=None, source_hash=None):
    meta = {}
    if source_hash:
        meta["sillon.code.version"] = {
            "logic_version": "logic1",
            "files": {"run.py": {"source_hash": source_hash, "logic_hash": "l1"}},
        }
    return SimulationTable(
        uuid=uuid,
        name=name,
        date="2026-06-01-10:00:00",
        started_at="2026-06-01T10:00:00+01:00",
        parameters={"degree": degree},
        results={"rmse": 0.5, "field": "field"},
        meta_data=meta,
        tag=["sweep"],
        note=["a note"],
        parents=parents or [],
        runtime="0:00:01",
        status="SUCCESS",
        platform="python",
        hostname="origin-host",
        organisation="",
        author="someone",
        project="Origin",
        hashes={},
        sillonversion="1.5.0",
        logic_version="logic1",
    )


def _project(path: Path, *, with_data=True, rows=None):
    """A project on disk: config, database, and the data trees."""
    sillon = path / ".sillon"
    sillon.mkdir(parents=True, exist_ok=True)
    (sillon / "config.toml").write_text(
        '[Environment]\nproject_id = "proj-1"\nproject_name = "Origin"\n'
        '\n[storage]\nstorage_root = ".sillon"\n'
    )
    if rows is None:
        rows = [_row(RUN_A, "deg3", 3, source_hash=SOURCE_HASH)]
    # Read off the objects before they are committed: afterwards they are
    # detached from the session and every attribute access raises.
    uuids = [row.uuid for row in rows]

    engine = migrate_schema(make_engine(sillon / "database.sql"))
    with Session(engine) as session:
        for row in rows:
            session.add(row)
        session.commit()

    if with_data:
        for uuid in uuids or [RUN_A]:
            glob_dir = sillon / "glob" / uuid
            glob_dir.mkdir(parents=True, exist_ok=True)
            with h5py.File(glob_dir / "glob.hdf5", "w") as g:
                g.create_dataset("result/field", data=np.arange(32, dtype="float64"))
        art = sillon / "artifact" / RUN_A / ARTIFACT_ID
        art.mkdir(parents=True, exist_ok=True)
        (art / "mesh.txt").write_text("mesh bytes")
        fig = sillon / "figure" / RUN_A / FIGURE_ID
        fig.mkdir(parents=True, exist_ok=True)
        (fig / "fit.png").write_bytes(b"\x89PNG fake")
        (sillon / "sources").mkdir(parents=True, exist_ok=True)
        (sillon / "sources" / SOURCE_HASH).write_text("print('hello')")
    return engine, sillon


@pytest.fixture()
def origin(tmp_path):
    path = tmp_path / "origin"
    rows = [
        _row(RUN_A, "deg3", 3, source_hash=SOURCE_HASH),
        _row(RUN_B, "deg4", 4, parents=[{"uuid": RUN_A, "name": "deg3"}]),
    ]
    engine, storage = _project(path, rows=rows)
    with Session(engine) as session:
        run_a = session.exec(
            select(SimulationTable).where(SimulationTable.uuid == RUN_A)
        ).one()
        session.add(ArtifactTable(name="mesh", hsh="h1", path=ARTIFACT_ID, run_id=run_a.id))
        session.add(
            FigureTable(
                name="fit", hsh="h2", path=FIGURE_ID,
                meta={"used": ["degree"], "caption": "c"}, date="2026-06-01-10:00:00",
                run_id=run_a.id,
            )
        )
        session.commit()
    return {"path": path, "engine": engine, "storage": storage}


@pytest.fixture()
def empty_dest(tmp_path):
    path = tmp_path / "dest"
    engine, storage = _project(path, with_data=False, rows=[])
    return {"path": path, "engine": engine, "storage": storage}


def _export(origin, dest=None, **kwargs):
    return export_bundle(
        origin["engine"], origin["storage"], origin["path"],
        dest=dest or origin["path"].parent / "out.sillon", **kwargs,
    )


# ==========================================
#                 THE FORMAT
# ==========================================
def test_the_layout_mirrors_the_on_disk_layout(origin):
    """Which is why importing is a copy and not dataset surgery."""
    result = _export(origin)
    with zipfile.ZipFile(result["path"]) as archive:
        names = set(archive.namelist())

    assert MANIFEST_NAME in names
    assert f"runs/{RUN_A}/run.json" in names
    assert f"runs/{RUN_A}/glob/glob.hdf5" in names
    assert f"runs/{RUN_A}/artifact/{ARTIFACT_ID}/mesh.txt" in names
    assert f"runs/{RUN_A}/figure/{FIGURE_ID}/fit.png" in names
    assert f"sources/{SOURCE_HASH}" in names


def test_the_manifest_says_what_it_is_and_where_it_came_from(origin):
    manifest = read_manifest(_export(origin)["path"])
    assert manifest["bundle_format"] == BUNDLE_FORMAT
    assert manifest["source"]["project_id"] == "proj-1"
    assert manifest["source"]["project_name"] == "Origin"
    assert manifest["source"]["hostname"] == "origin-host"
    assert manifest["with_data"] is True
    assert {r["uuid"] for r in manifest["runs"]} == {RUN_A, RUN_B}


def test_a_report_zip_is_refused_with_an_explanation(tmp_path):
    """The two archive kinds are easy to confuse; one is not importable."""
    fake = tmp_path / "looks-like-one.sillon"
    with zipfile.ZipFile(fake, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("report.md", "# hi")

    with pytest.raises(BundleError) as excinfo:
        read_manifest(fake)
    assert "report" in str(excinfo.value)


def test_a_bundle_from_the_future_is_refused_not_half_read(tmp_path):
    future = tmp_path / "future.sillon"
    with zipfile.ZipFile(future, "w") as archive:
        archive.writestr(
            MANIFEST_NAME, json.dumps({"bundle_format": BUNDLE_FORMAT + 1})
        )
    with pytest.raises(BundleError, match="newer sillon"):
        read_manifest(future)


def test_a_file_that_is_not_a_zip(tmp_path):
    junk = tmp_path / "junk.sillon"
    junk.write_text("not a zip")
    with pytest.raises(BundleError, match="not a sillon bundle"):
        read_manifest(junk)


def test_a_missing_file(tmp_path):
    with pytest.raises(BundleError, match="No such bundle"):
        read_manifest(tmp_path / "nope.sillon")


def test_the_default_name_is_readable_in_a_shared_folder(tmp_path):
    _project(tmp_path / "p", with_data=False, rows=[])
    name = default_bundle_name(tmp_path / "p", "dalaran-8.local")
    assert name.startswith("Origin~dalaran-8.local~")
    assert name.endswith(".sillon")
    # No colons or plus signs: they either collide with the separator or read
    # as part of the time.
    assert ":" not in name and "+" not in name


# ==========================================
#                 EXPORTING
# ==========================================
def test_exporting_nothing_is_an_error_not_an_empty_bundle(empty_dest):
    with pytest.raises(BundleError, match="no runs matched"):
        export_bundle(
            empty_dest["engine"], empty_dest["storage"], empty_dest["path"],
            dest=empty_dest["path"] / "out.sillon",
        )


def test_a_filter_selects_a_subset(origin):
    result = _export(origin, parameters={"degree": 4})
    assert result["runs"] == ["deg4"]


def test_no_data_writes_an_index_only_bundle(origin):
    result = _export(origin, with_data=False)
    assert result["with_data"] is False
    with zipfile.ZipFile(result["path"]) as archive:
        names = archive.namelist()
    assert any(n.endswith("run.json") for n in names)
    assert not any("/glob/" in n for n in names)
    assert not any(n.startswith("sources/") for n in names)


def test_data_a_row_claims_but_does_not_have_is_reported(tmp_path):
    """A pruned run exports its record; saying so beats looking complete."""
    path = tmp_path / "pruned"
    engine, storage = _project(path, with_data=False, rows=[_row(RUN_A, "deg3", 3)])
    result = export_bundle(engine, storage, path, dest=tmp_path / "out.sillon")
    assert result["skipped_data"] == [{"uuid": RUN_A, "group": "glob"}]


def test_dest_can_be_a_directory(origin, tmp_path):
    folder = tmp_path / "outbox"
    folder.mkdir()
    result = _export(origin, dest=folder)
    assert result["path"].parent == folder
    assert result["path"].name.startswith("Origin~")


def test_inspect_does_not_need_a_project(origin):
    described = inspect_bundle(_export(origin)["path"])
    assert described["run_count"] == 2
    assert described["project_name"] == "Origin"
    assert described["has_data"] is True


# ==========================================
#                 IMPORTING
# ==========================================
def test_a_run_arrives_with_its_identity_intact(origin, empty_dest):
    bundle = _export(origin)["path"]
    import_from(empty_dest["engine"], empty_dest["storage"], bundle)

    rows = {e["name"]: e for e in select_run_index(empty_dest["engine"])}
    assert set(rows) == {"deg3", "deg4"}
    arrived = rows["deg3"]
    assert arrived["uuid"] == RUN_A
    assert arrived["date"] == "2026-06-01-10:00:00"
    assert arrived["started_at"] == "2026-06-01T10:00:00+01:00"
    assert arrived["hostname"] == "origin-host"
    # The version that *wrote* the run, not the one that filed it.
    assert arrived["sillonversion"] == "1.5.0"
    assert arrived["tag"] == ["sweep"]
    assert arrived["note"] == ["a note"]


def test_the_data_trees_land_where_readers_look(origin, empty_dest):
    import_from(empty_dest["engine"], empty_dest["storage"], _export(origin)["path"])
    storage = empty_dest["storage"]

    with h5py.File(storage / "glob" / RUN_A / "glob.hdf5", "r") as g:
        assert np.array_equal(g["result/field"][()], np.arange(32, dtype="float64"))
    assert (storage / "artifact" / RUN_A / ARTIFACT_ID / "mesh.txt").read_text() == "mesh bytes"
    assert (storage / "figure" / RUN_A / FIGURE_ID / "fit.png").read_bytes() == b"\x89PNG fake"
    assert (storage / "sources" / SOURCE_HASH).read_text() == "print('hello')"


def test_child_rows_are_repointed_at_the_new_primary_key(origin, empty_dest):
    """The integer PK is machine-local; the children must follow the new one."""
    import_from(empty_dest["engine"], empty_dest["storage"], _export(origin)["path"])
    with Session(empty_dest["engine"]) as session:
        run = session.exec(
            select(SimulationTable).where(SimulationTable.uuid == RUN_A)
        ).one()
        artifacts = session.exec(
            select(ArtifactTable).where(ArtifactTable.run_id == run.id)
        ).all()
        figures = session.exec(
            select(FigureTable).where(FigureTable.run_id == run.id)
        ).all()
    assert [a.name for a in artifacts] == ["mesh"]
    assert [f.name for f in figures] == ["fit"]
    # The path column is a uuid folder name, which is why the tree could move.
    assert artifacts[0].path == ARTIFACT_ID
    assert figures[0].meta == {"used": ["degree"], "caption": "c"}


def test_importing_twice_adds_nothing(origin, empty_dest):
    bundle = _export(origin)["path"]
    first = import_from(empty_dest["engine"], empty_dest["storage"], bundle)
    second = import_from(empty_dest["engine"], empty_dest["storage"], bundle)

    assert first["imported"] == 2
    assert second["imported"] == 0
    assert len(second["already_here"]) == 2
    assert len(select_run_index(empty_dest["engine"])) == 2


def test_a_dry_run_changes_nothing(origin, empty_dest):
    bundle = _export(origin)["path"]
    plan = import_from(empty_dest["engine"], empty_dest["storage"], bundle, dry_run=True)
    assert plan["dry_run"] is True
    assert len(plan["new"]) == 2
    assert select_run_index(empty_dest["engine"]) == []
    assert not (empty_dest["storage"] / "glob").exists()


# ==========================================
#              NAME COLLISIONS
# ==========================================
def test_a_taken_name_is_suffixed_with_where_it_came_from(origin, tmp_path):
    local = tmp_path / "local"
    engine, storage = _project(
        local, with_data=False,
        rows=[_row("cccccccc-0000-0000-0000-00000000000c", "deg3", 99)],
    )
    result = import_from(engine, storage, _export(origin)["path"])

    names = {e["name"]: e for e in select_run_index(engine)}
    assert set(names) == {"deg3", "deg3~origin-host", "deg4"}
    # The local run keeps its name *and* its values.
    assert names["deg3"]["parameters"]["degree"] == 99
    assert names["deg3~origin-host"]["parameters"]["degree"] == 3
    assert result["renamed"] == [{"uuid": RUN_A, "from": "deg3", "to": "deg3~origin-host"}]


def test_two_incoming_runs_with_the_same_name(tmp_path):
    """Both must land; the second cannot reuse the first's new name."""
    origin_path = tmp_path / "origin"
    engine, storage = _project(
        origin_path, with_data=False,
        rows=[_row(RUN_A, "deg3", 3), _row(RUN_B, "deg3", 4)],
    )
    bundle = export_bundle(engine, storage, origin_path, dest=tmp_path / "o.sillon")

    local = tmp_path / "local"
    dest_engine, dest_storage = _project(
        local, with_data=False,
        rows=[_row("dddddddd-0000-0000-0000-00000000000d", "deg3", 99)],
    )
    import_from(dest_engine, dest_storage, bundle["path"])

    names = sorted(e["name"] for e in select_run_index(dest_engine))
    assert names == ["deg3", "deg3~origin-host", "deg3~origin-host_2"]


def test_lineage_survives_the_rename(origin, tmp_path):
    """The edge is followed by uuid, so suffixing cannot bend it."""
    import sillonlab as sl

    local = tmp_path / "local"
    engine, storage = _project(
        local, with_data=False,
        rows=[_row("cccccccc-0000-0000-0000-00000000000c", "deg3", 99)],
    )
    import_from(engine, storage, _export(origin)["path"])

    project = sl.load_project(local)
    parent = project.get("deg4").parents()[0]
    assert parent.uuid == RUN_A
    assert parent.name == "deg3~origin-host"
    assert parent.parameters["degree"] == 3  # not the local namesake's 99


# ==========================================
#           STUBS AND DANGLING EDGES
# ==========================================
def test_no_data_import_records_the_runs_as_stubs(origin, empty_dest):
    bundle = _export(origin)["path"]
    result = import_from(empty_dest["engine"], empty_dest["storage"], bundle, with_data=False)

    assert result["imported"] == 2
    assert len(result["stubs"]) == 2
    assert result["files_copied"] == 0
    assert not (empty_dest["storage"] / "glob").exists()
    # The records are all there.
    assert {e["name"] for e in select_run_index(empty_dest["engine"])} == {"deg3", "deg4"}


def test_a_child_without_its_parent_reports_the_dangling_edge(origin, empty_dest):
    """Export the child only; the edge is true but unwalkable."""
    bundle = _export(origin, run_names=["deg4"])["path"]
    result = import_from(empty_dest["engine"], empty_dest["storage"], bundle)

    assert result["imported"] == 1
    assert result["parents_missing"] == [
        {"run": "deg4", "parent_uuid": RUN_A, "parent_name": "deg3"}
    ]
    # The edge is kept, because it is still a true statement.
    row = select_run_index(empty_dest["engine"])[0]
    assert row["parents"] == [{"uuid": RUN_A, "name": "deg3"}]


def test_a_parent_in_the_same_bundle_is_not_reported_missing(origin, empty_dest):
    result = import_from(
        empty_dest["engine"], empty_dest["storage"], _export(origin)["path"]
    )
    assert result["parents_missing"] == []


def test_a_parent_already_in_the_destination_is_not_reported_missing(origin, tmp_path):
    local = tmp_path / "local"
    engine, storage = _project(local, with_data=False, rows=[_row(RUN_A, "deg3", 3)])
    result = import_from(engine, storage, _export(origin, run_names=["deg4"])["path"])
    assert result["parents_missing"] == []


# ==========================================
#            THE SOURCE INTERFACE
# ==========================================
def test_a_source_must_be_opened(origin):
    source = BundleSource(_export(origin)["path"])
    with pytest.raises(BundleError, match="context manager"):
        source.read_run(RUN_A)


def test_a_source_blob_already_present_is_not_rewritten(origin, empty_dest):
    """Content-addressed: the name is the hash, so it cannot differ."""
    blob = empty_dest["storage"] / "sources" / SOURCE_HASH
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_text("print('hello')")

    result = import_from(
        empty_dest["engine"], empty_dest["storage"], _export(origin)["path"]
    )
    assert result["sources_copied"] == 0
    assert blob.read_text() == "print('hello')"
    # And no temp file was left behind.
    assert not list(blob.parent.glob(".*tmp"))
