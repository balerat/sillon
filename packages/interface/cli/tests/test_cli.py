"""Smoke tests for the silloncli commands against a synthetic project.

Commands are invoked through their `command(engine, storage_root, args)` entry
point (no daemon, no subprocess), mirroring how main.py dispatches them.
"""

import h5py
import numpy as np
import pytest
from sqlmodel import SQLModel, Session, create_engine

from silloncommon.database import SimulationTable, ArtifactTable
from silloncore.project_paths import resolve_engine, resolve_storage_root

import silloncli.commands.search as search
import silloncli.commands.grab as grab
import silloncli.commands.prune as prune
import silloncli.commands.report as report
import silloncli.commands.show as show
import silloncli.commands.add as add

RUN_UUID = "cli-uuid-a"
ARTIFACT_ID = "cli-art-1"


@pytest.fixture()
def project(tmp_path):
    sillon_dir = tmp_path / ".sillon"
    glob_dir = sillon_dir / "glob" / RUN_UUID
    artifact_dir = sillon_dir / "artifact" / RUN_UUID / ARTIFACT_ID
    glob_dir.mkdir(parents=True)
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "mesh.txt").write_text("artifact content")

    with h5py.File(glob_dir / "glob.hdf5", "w") as g:
        g.create_dataset("result/coef", data=np.array([1.0, 2.0]))

    engine = create_engine("sqlite:///" + str(sillon_dir / "database.sql"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            SimulationTable(
                uuid=RUN_UUID,
                name="exp",
                date="2026-06-01-10:00:00",
                parameters={"optimizer": "adam", "lr": 0.01},
                results={"coef": "coef"},
                meta_data={},
                tag=[],
                note=[],
                runtime="0:00:01",
                status="SUCCESS",
                platform="python",
                hostname="host",
                organisation="",
                author="t",
                project="p",
                hashes={},
                sillonversion="0.2.0",
                artifacts=[ArtifactTable(name="mesh", hsh="h", path=ARTIFACT_ID)],
            )
        )
        session.commit()
    engine.dispose()

    # Resolve exactly like the CLI entrypoint does.
    return resolve_engine(tmp_path), resolve_storage_root(tmp_path), tmp_path


def test_search_by_parameter(project):
    engine, storage_root, _ = project
    names = search.command(engine, storage_root, {"parameter": ["optimizer=adam"]})
    assert names == ["exp"]


def test_search_by_result_and_artifact(project):
    engine, storage_root, _ = project
    assert search.command(engine, storage_root, {"result": ["coef"]}) == ["exp"]
    assert search.command(engine, storage_root, {"artifact": ["mesh"]}) == ["exp"]
    assert search.command(engine, storage_root, {"result": ["ghost"]}) == []


def test_grab_result(project, tmp_path):
    engine, storage_root, _ = project
    dest = tmp_path / "out"
    path = grab.command(
        engine, storage_root, {"run_name": "exp", "result": "coef", "dest": str(dest)}
    )
    assert path == dest / "coef.npy"
    assert np.allclose(np.load(path), [1.0, 2.0])


def test_report_bundle(project, tmp_path):
    import zipfile

    engine, storage_root, _ = project
    out = tmp_path / "exp.zip"
    path = report.command(
        engine, storage_root, {"run_name": "exp", "dest": str(out), "with_data": False}
    )
    assert path.exists()
    with zipfile.ZipFile(path) as z:
        assert "manifest.json" in z.namelist()
        assert "report.md" in z.namelist()


def test_prune_refuses_without_selector(project):
    engine, storage_root, _ = project
    result = prune.command(engine, storage_root, {"run_id": None, "older_than": None})
    assert result["status"] == "error"


def test_prune_keep_metadata(project):
    engine, storage_root, base = project
    result = prune.command(
        engine, storage_root, {"run_id": ["exp"], "older_than": None}
    )
    assert result["status"] == "success"
    assert result["pruned"] == ["exp"]
    assert not (base / ".sillon" / "glob" / RUN_UUID).exists()
    # metadata kept: the run is still searchable
    assert search.command(engine, storage_root, {"parameter": ["optimizer=adam"]}) == ["exp"]


def test_add_and_show(project, capsys):
    engine, storage_root, _ = project
    add.command(engine, storage_root, {"run_name": ["exp"], "note": ["hi"], "tag": ["t"]})
    show.command(
        engine, storage_root, {"run_name": ["exp"], "parameter": ["%all%"], "result": None, "metadata": None}
    )
    out = capsys.readouterr().out
    assert "optimizer" in out
