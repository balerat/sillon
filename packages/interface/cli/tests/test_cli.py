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
import silloncli.commands.delete as delete

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
                meta_data={"sillon.language": "python"},
                tag=["prod"],
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


def test_search_by_metadata_tag_status_date(project):
    engine, storage_root, _ = project
    assert search.command(engine, storage_root, {"meta": ["sillon.language=python"]}) == ["exp"]
    assert search.command(engine, storage_root, {"tag": ["prod"]}) == ["exp"]
    assert search.command(engine, storage_root, {"status": "SUCCESS"}) == ["exp"]
    assert search.command(engine, storage_root, {"status": "FAILED"}) == []
    assert search.command(engine, storage_root, {"after": "2026-05-01"}) == ["exp"]
    assert search.command(engine, storage_root, {"before": "2026-05-01"}) == []


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


def test_delete_run(project):
    engine, storage_root, base = project
    result = delete.command(engine, storage_root, {"run_name": ["exp"], "yes": True})
    assert result[0]["status"] == "success"
    assert result[0]["deleted"] == "exp"
    # storage gone and run no longer in the DB
    assert not (base / ".sillon" / "glob" / RUN_UUID).exists()
    assert search.command(engine, storage_root, {"parameter": ["optimizer=adam"]}) == []


def test_add_and_show(project, capsys):
    engine, storage_root, _ = project
    add.command(engine, storage_root, {"run_name": ["exp"], "note": ["hi"], "tag": ["t"]})
    show.command(
        engine, storage_root, {"run_name": ["exp"], "parameter": ["%all%"], "result": None, "metadata": None}
    )
    out = capsys.readouterr().out
    assert "optimizer" in out


# ==========================================
#          POLISH: new commands + flags
# ==========================================

import silloncli.commands.rename as rename
import silloncli.commands.whose as whose
import silloncli.commands.context as context


def test_show_full_card(project, capsys):
    engine, storage_root, _ = project
    # No section flag -> the full themed run card.
    show.command(engine, storage_root, {"run_name": ["exp"]})
    out = capsys.readouterr().out
    assert "exp" in out
    assert "Results" in out


def test_show_unknown_run(project, capsys):
    engine, storage_root, _ = project
    show.command(engine, storage_root, {"run_name": ["ghost"]})
    out = capsys.readouterr().out
    assert "not found" in out


def test_show_by_uuid_prefix(project, capsys):
    engine, storage_root, _ = project
    # The fixture run's uuid is 'cli-uuid-a'; a unique prefix resolves it.
    show.command(engine, storage_root, {"run_name": ["cli-uuid"]})
    out = capsys.readouterr().out
    assert "exp" in out
    assert "Results" in out


def test_rename_command(project, capsys):
    engine, storage_root, _ = project
    result = rename.command(engine, storage_root, {"run_name": "exp", "new_name": "exp_renamed"})
    assert result["status"] == "success"
    assert search.command(engine, storage_root, {"parameter": ["optimizer=adam"]}) == ["exp_renamed"]


def test_rename_command_rejects_clash(project, capsys):
    engine, storage_root, _ = project
    # rename exp -> exp (itself) is treated as taken -> error, run unchanged
    result = rename.command(engine, storage_root, {"run_name": "exp", "new_name": "exp"})
    assert result["status"] == "error"


def test_whose_command(project, capsys):
    engine, storage_root, _ = project
    matches = whose.command(engine, storage_root, {"file": "h"})  # artifact 'mesh' hsh is 'h'
    assert matches[0]["run_name"] == "exp"
    assert matches[0]["name"] == "mesh"


def test_whose_unknown(project, capsys):
    engine, storage_root, _ = project
    assert whose.command(engine, storage_root, {"file": "nope"}) == []


def test_context_overview_themed(project, capsys):
    engine, storage_root, _ = project
    context.command(engine, storage_root, {"run_name": []})
    out = capsys.readouterr().out
    assert "exp" in out


def test_prune_delete_metadata_with_yes(project):
    engine, storage_root, base = project
    result = prune.command(
        engine, storage_root,
        {"run_id": ["exp"], "older_than": None, "delete_metadata": True, "yes": True},
    )
    assert result["status"] == "success"
    assert not result["kept_metadata"]
    # fully gone from the DB
    assert search.command(engine, storage_root, {"parameter": ["optimizer=adam"]}) == []
