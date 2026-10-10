"""What `check` notices, and what `--repair` is allowed to touch.

Most of what sillon records is a cross-reference, and each one can come apart:
a pruned run, a half-finished copy, a child imported without its parent, a
project moved while its data was on a disk that is not here. None of it is
fatal and all of it is confusing when you meet it as a failed read months
later.

The repair half is deliberately narrow. Nothing it does can lose work — if
`check` is wrong about a finding, acting on it must cost nothing — so anything
whose fix is a judgement call is reported and left alone.
"""

import h5py
import numpy as np
import pytest
from sqlmodel import Session, SQLModel, create_engine

from silloncommon import registry
from silloncommon.database import SimulationTable, sqlite_url
from silloncore.check import check_project, repair_project
from silloncore.project_paths import resolve_engine, resolve_storage_root

RUN_A = "chk-a"
RUN_B = "chk-b"
SOURCE_HASH = "a" * 64


def _row(uuid, name, *, results=None, parents=None, artifacts=False,
         figures=False, source_hash=None):
    meta = {}
    if source_hash:
        meta["sillon.code.version"] = {
            "logic_version": "l1",
            "files": {"run.py": {"source_hash": source_hash}},
        }
    return SimulationTable(
        uuid=uuid,
        name=name,
        date="2026-06-01-10:00:00",
        started_at="2026-06-01T10:00:00+01:00",
        parameters={"degree": 3},
        results=results if results is not None else {"field": "field"},
        meta_data=meta,
        tag=[],
        note=[],
        parents=parents or [],
        runtime="0:00:01",
        status="SUCCESS",
        platform="python",
        hostname="h",
        organisation="",
        author="t",
        project="Checkme",
        hashes={},
        sillonversion="2.1.0",
    )


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


@pytest.fixture()
def project(tmp_path):
    """A healthy project: one run, its data, its source blob, registered."""
    path = tmp_path / "proj"
    sillon = path / ".sillon"
    sillon.mkdir(parents=True)
    (sillon / "config.toml").write_text(
        '[Environment]\nproject_id = "chk-1"\nproject_name = "Checkme"\n'
        '\n[storage]\nstorage_root = ".sillon"\n'
    )
    glob_dir = sillon / "glob" / RUN_A
    glob_dir.mkdir(parents=True)
    with h5py.File(glob_dir / "glob.hdf5", "w") as g:
        g.create_dataset("result/field", data=np.arange(8, dtype="float64"))
    (sillon / "sources").mkdir()
    (sillon / "sources" / SOURCE_HASH).write_text("print('hi')")

    engine = create_engine(sqlite_url(sillon / "database.sql"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(_row(RUN_A, "deg3", source_hash=SOURCE_HASH))
        session.commit()
    engine.dispose()

    registry.upsert("chk-1", path, "Checkme", sillon, sillon)
    return path


def _check(path):
    return check_project(resolve_engine(path), resolve_storage_root(path), path)


def _repair(path):
    return repair_project(resolve_engine(path), resolve_storage_root(path), path)


def _kinds(result):
    return {f["kind"] for f in result["findings"]}


# ==========================================
#                  HEALTHY
# ==========================================
def test_a_healthy_project_reports_nothing(project):
    result = _check(project)
    assert result["healthy"] is True
    assert result["findings"] == []
    assert result["run_count"] == 1


def test_an_empty_project_is_healthy(tmp_path):
    """A project `init` just made has no runs and nothing wrong with it."""
    from silloncore.projects import create_project

    info = create_project(tmp_path / "fresh", project_name="Fresh")
    result = _check(info["path"])
    assert result["healthy"] is True
    assert result["run_count"] == 0


# ==========================================
#              MISSING DATA
# ==========================================
def test_a_run_whose_glob_is_gone(project):
    import shutil

    shutil.rmtree(project / ".sillon" / "glob" / RUN_A)
    result = _check(project)
    assert "run_data_missing" in _kinds(result)
    finding = next(f for f in result["findings"] if f["kind"] == "run_data_missing")
    assert finding["detail"]["run"] == "deg3"
    assert finding["detail"]["groups"] == ["glob"]
    # Not repairable: the fix is to re-run it or delete it, and that is a
    # decision only the person can make.
    assert finding["repairable"] is False


def test_a_run_with_no_results_needs_no_glob(project):
    """A run that only logged parameters is complete without one."""
    engine = resolve_engine(project)
    with Session(engine) as session:
        session.add(_row(RUN_B, "params_only", results={}))
        session.commit()
    assert "run_data_missing" not in _kinds(_check(project))


def test_a_missing_artifact_directory(project):
    from silloncommon.database import ArtifactTable

    engine = resolve_engine(project)
    with Session(engine) as session:
        from sqlmodel import select

        run = session.exec(
            select(SimulationTable).where(SimulationTable.uuid == RUN_A)
        ).one()
        session.add(ArtifactTable(name="mesh", hsh="h", path="x", run_id=run.id))
        session.commit()
    finding = next(f for f in _check(project)["findings"] if f["kind"] == "run_data_missing")
    assert "artifact" in finding["detail"]["groups"]


# ==========================================
#              ORPHANED DATA
# ==========================================
def test_data_with_no_run_behind_it(project):
    orphan = project / ".sillon" / "glob" / "no-such-run"
    orphan.mkdir(parents=True)
    (orphan / "glob.hdf5").write_bytes(b"x" * 100)

    result = _check(project)
    finding = next(f for f in result["findings"] if f["kind"] == "orphan_data")
    assert finding["severity"] == "tidy"
    assert finding["repairable"] is True


def test_repair_removes_orphaned_data(project):
    orphan = project / ".sillon" / "glob" / "no-such-run"
    orphan.mkdir(parents=True)
    (orphan / "glob.hdf5").write_bytes(b"x" * 100)

    result = _repair(project)
    assert not orphan.exists()
    assert result["freed_bytes"] >= 100
    assert "orphan_data" not in {f["kind"] for f in result["remaining"]}
    # The real run's data was not touched.
    assert (project / ".sillon" / "glob" / RUN_A / "glob.hdf5").is_file()


# ==========================================
#                 LINEAGE
# ==========================================
def test_a_parent_that_is_not_here(project):
    engine = resolve_engine(project)
    with Session(engine) as session:
        session.add(
            _row(RUN_B, "child", parents=[{"uuid": "absent", "name": "base"}],
                 results={})
        )
        session.commit()

    finding = next(f for f in _check(project)["findings"] if f["kind"] == "parent_missing")
    assert finding["detail"]["parent_name"] == "base"
    assert finding["severity"] == "stale"
    # The edge is a true statement; deleting it is not a repair.
    assert finding["repairable"] is False


def test_a_parent_that_is_here_is_not_reported(project):
    engine = resolve_engine(project)
    with Session(engine) as session:
        session.add(
            _row(RUN_B, "child", parents=[{"uuid": RUN_A, "name": "deg3"}], results={})
        )
        session.commit()
    assert "parent_missing" not in _kinds(_check(project))


# ==========================================
#               DUPLICATES
# ==========================================
def _add_duplicate_uuid(project, name="shadow"):
    """Insert a second row with an existing uuid.

    Only possible on a database that predates the unique index, which is the
    point: `check` exists to find what is already in there. A fresh database
    refuses the insert outright, which is §1.3 working.
    """
    engine = create_engine(sqlite_url(project / ".sillon" / "database.sql"))
    with Session(engine) as session:
        session.add(_row(RUN_A, name, results={}))
        session.commit()
    engine.dispose()


@pytest.fixture()
def legacy_project(tmp_path, project):
    """`project`, with its uuid uniqueness dropped as an older sillon had it."""
    engine = create_engine(sqlite_url(project / ".sillon" / "database.sql"))
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_simulationtable_uuid_unique")
    engine.dispose()
    return project


def test_two_rows_with_the_same_uuid(legacy_project):
    """Invisible to `.first()` readers while the index still counts it."""
    _add_duplicate_uuid(legacy_project)

    finding = next(
        f for f in _check(legacy_project)["findings"] if f["kind"] == "duplicate_uuid"
    )
    assert finding["severity"] == "broken"
    assert set(finding["detail"]["runs"]) == {"deg3", "shadow"}


def test_a_fresh_database_refuses_the_duplicate_outright(project):
    """So `check` only ever meets one that predates the guard."""
    from sqlalchemy.exc import IntegrityError

    resolve_engine(project)  # migrates, creating the unique index
    with pytest.raises(IntegrityError):
        _add_duplicate_uuid(project)


def test_two_rows_with_the_same_name(project):
    engine = resolve_engine(project)
    with Session(engine) as session:
        session.add(_row(RUN_B, "deg3", results={}))
        session.commit()
    assert "duplicate_name" in _kinds(_check(project))


# ==========================================
#                 SOURCES
# ==========================================
def test_a_source_a_code_version_refers_to_but_is_not_stored(project):
    (project / ".sillon" / "sources" / SOURCE_HASH).unlink()
    finding = next(f for f in _check(project)["findings"] if f["kind"] == "source_missing")
    assert finding["detail"]["hashes"] == [SOURCE_HASH]
    assert finding["repairable"] is False


def test_a_stored_source_no_run_refers_to(project):
    """`prune` has never cleaned sources/, so these accumulate."""
    (project / ".sillon" / "sources" / ("b" * 64)).write_text("orphan")
    finding = next(f for f in _check(project)["findings"] if f["kind"] == "orphan_source")
    assert finding["severity"] == "tidy"
    assert finding["repairable"] is True


def test_repair_removes_orphaned_sources_but_keeps_referenced_ones(project):
    orphan = project / ".sillon" / "sources" / ("b" * 64)
    orphan.write_text("orphan")

    _repair(project)
    assert not orphan.exists()
    assert (project / ".sillon" / "sources" / SOURCE_HASH).is_file()


# ==========================================
#            STORAGE AND REGISTRY
# ==========================================
def test_a_storage_root_that_is_not_there(tmp_path):
    """The data disk is gone, so the database is gone with it.

    This is the case `check` exists for, and it must work with no engine at
    all rather than failing to open the thing it is meant to diagnose.
    """
    import shutil

    from silloncore.projects import create_project

    external = tmp_path / "disk" / "store"
    info = create_project(tmp_path / "proj", project_name="P", storage_root=external)
    shutil.rmtree(tmp_path / "disk")

    result = check_project(None, resolve_storage_root(info["path"]), info["path"])

    kinds = {f["kind"] for f in result["findings"]}
    assert "storage_root_missing" in kinds
    assert "database_unreadable" in kinds
    assert result["healthy"] is False
    assert result["run_count"] == 0


def test_a_registry_row_pointing_somewhere_else(project):
    registry.upsert("chk-1", project.parent / "moved", "Checkme", project, project)
    finding = next(f for f in _check(project)["findings"] if f["kind"] == "registry_stale")
    assert finding["repairable"] is True


def test_repair_re_registers_the_project(project):
    registry.upsert("chk-1", project.parent / "moved", "Checkme", project, project)
    _repair(project)

    rows = [e for e in registry.entries() if e["project_id"] == "chk-1"]
    assert len(rows) == 1
    assert rows[0]["project_path"] == str(project.resolve())


def test_an_unregistered_project(tmp_path):
    """A project copied from another machine, never listed here."""
    from silloncore.projects import create_project

    info = create_project(tmp_path / "foreign", project_name="Foreign")
    registry.prune()
    # Remove the row create_project made, to simulate a plain directory copy.
    raw = registry.registry_path()
    raw.write_text("")

    result = _check(info["path"])
    assert "registry_missing" in _kinds(result)


def test_a_project_with_no_id_cannot_be_recognised_after_a_move(tmp_path):
    from silloncommon.database import make_engine, migrate_schema

    path = tmp_path / "old"
    (path / ".sillon").mkdir(parents=True)
    (path / ".sillon" / "config.toml").write_text("[storage]\n")
    migrate_schema(make_engine(path / ".sillon" / "database.sql")).dispose()

    assert "no_project_id" in _kinds(_check(path))


# ==========================================
#              REPAIR IS NARROW
# ==========================================
def test_repair_never_removes_a_run(project):
    import shutil

    shutil.rmtree(project / ".sillon" / "glob" / RUN_A)
    engine = resolve_engine(project)
    with Session(engine) as session:
        session.add(
            _row(RUN_B, "child", parents=[{"uuid": "absent", "name": "base"}],
                 results={})
        )
        session.commit()

    _repair(project)

    from silloncommon.database import select_run_index

    assert {e["name"] for e in select_run_index(resolve_engine(project))} == {
        "deg3", "child",
    }


def test_repair_on_a_healthy_project_does_nothing(project):
    result = _repair(project)
    assert result["repaired"] == []
    assert result["freed_bytes"] == 0
    assert result["remaining"] == []


def test_findings_are_ordered_worst_first(legacy_project):
    """So the top of the list is the thing to look at."""
    (legacy_project / ".sillon" / "sources" / ("b" * 64)).write_text("orphan")
    _add_duplicate_uuid(legacy_project)  # broken

    severities = [f["severity"] for f in _check(legacy_project)["findings"]]
    assert severities[0] == "broken"
    assert severities == sorted(severities, key=["broken", "stale", "tidy"].index)
