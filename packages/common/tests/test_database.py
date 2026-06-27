"""Unit tests for the silloncommon data layer (no server required)."""

import pytest
from sqlmodel import SQLModel, Session, create_engine

from silloncommon.database import (
    SimulationTable,
    ArtifactTable,
    AnalysisTable,
    select_run_snapshot,
    select_run_index,
    select_run_identities,
    next_available_name,
    db_append_note_tag,
    db_append_metadata,
    db_insert_analysis,
    db_delete_runs,
    check_hashes_exists,
)


def _make_run(name, uuid, **overrides):
    base = dict(
        uuid=uuid,
        name=name,
        date="2026-06-01-10:00:00",
        parameters={"lr": 0.01, "optimizer": "adam"},
        results={"coef": "coef"},
        meta_data={"sillon.language": "python"},
        tag=["baseline"],
        note=["a note"],
        runtime="0:00:01",
        status="SUCCESS",
        platform="python",
        hostname="host",
        organisation="",
        author="tester",
        project="proj",
        hashes={},
        sillonversion="0.2.0",
    )
    base.update(overrides)
    return SimulationTable(**base)


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "database.sql"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run_a = _make_run("run_a", "uuid-a")
        run_a.artifacts = [ArtifactTable(name="mesh", hsh="hash-mesh", path="art-1")]
        session.add(run_a)
        session.add(_make_run("run_b", "uuid-b", parameters={"lr": 0.5}, results={}))
        session.commit()
    return engine


def test_select_run_snapshot_returns_links(engine):
    run, artifacts, figures, analyses = select_run_snapshot(engine, "run_a")
    assert run["name"] == "run_a"
    assert run["parameters"]["optimizer"] == "adam"
    assert [a["name"] for a in artifacts] == ["mesh"]
    assert figures == []
    assert analyses == []


def test_select_run_snapshot_by_uuid_and_missing(engine):
    run, *_ = select_run_snapshot(engine, "uuid-b")
    assert run["name"] == "run_b"
    assert select_run_snapshot(engine, "ghost") == (None, [], [], [])


def test_select_run_index(engine):
    index = {entry["name"]: entry for entry in select_run_index(engine)}
    # Rich, glob-free index: full columns + linked-item names.
    assert index["run_a"]["result_names"] == ["coef"]
    assert index["run_a"]["results"] == {"coef": "coef"}
    assert index["run_a"]["artifacts"] == ["mesh"]
    assert index["run_a"]["uuid"] == "uuid-a"
    assert index["run_a"]["status"] == "SUCCESS"
    assert index["run_a"]["tag"] == ["baseline"]
    assert index["run_a"]["meta_data"] == {"sillon.language": "python"}
    assert index["run_b"]["parameters"] == {"lr": 0.5}


def test_select_run_identities(engine):
    ids = {entry["name"]: entry for entry in select_run_identities(engine)}
    assert ids["run_a"]["uuid"] == "uuid-a"
    assert ids["run_a"]["date"] == "2026-06-01-10:00:00"


def test_next_available_name(engine):
    assert next_available_name(engine, "fresh") == "fresh"
    assert next_available_name(engine, "run_a") == "run_a_2"
    # in-flight names are honored on top of the database
    assert next_available_name(engine, "run_a", taken=["run_a_2"]) == "run_a_3"


def test_db_append_note_tag(engine):
    db_append_note_tag(engine, ["run_b"], notes=["hello"], tags=["t1"])
    run, *_ = select_run_snapshot(engine, "run_b")
    assert "hello" in run["note"]
    assert "t1" in run["tag"]


def test_db_append_metadata(engine):
    db_append_metadata(engine, ["run_b"], {"instrument": "laser"})
    run, *_ = select_run_snapshot(engine, "run_b")
    assert run["meta_data"]["instrument"] == "laser"


def test_db_insert_analysis(engine):
    run, *_ = select_run_snapshot(engine, "run_a")
    db_insert_analysis(engine, run["id"], "fit", pointer="fit", hsh="h", meta={"c": 1})
    _, _, _, analyses = select_run_snapshot(engine, "run_a")
    assert analyses[0]["name"] == "fit"
    assert analyses[0]["meta"] == {"c": 1}


def test_db_delete_runs(engine):
    deleted = db_delete_runs(engine, ["run_a"])
    assert deleted == ["run_a"]
    assert select_run_snapshot(engine, "run_a") == (None, [], [], [])
    # linked artifact is gone too
    with Session(engine) as session:
        from sqlmodel import select

        assert session.exec(select(ArtifactTable)).all() == []


def test_check_hashes_exists(engine):
    assert check_hashes_exists("hash-mesh", engine) == ("art-1", "hash-mesh")
    assert check_hashes_exists("nope", engine) is None
