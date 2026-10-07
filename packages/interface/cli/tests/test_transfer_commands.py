"""`sillon export` and `sillon import` through their CLI entry points.

The engine behaviour is covered elsewhere; what these pin is the part only the
CLI owns — the flags, the `KEY=VALUE` parsing, the directory-or-file `--dest`,
and that a bad bundle produces a message rather than a traceback. The commands
are driven the way `main.py` drives them, so an argument renamed in the parser
but not in the handler fails here.
"""

import h5py
import numpy as np
import pytest
from sqlmodel import Session, SQLModel, create_engine

from silloncommon.database import SimulationTable, sqlite_url
from silloncore.project_paths import resolve_engine, resolve_storage_root

import silloncli.commands.export as export
import silloncli.commands.import_cmd as import_cmd

RUN_A = "cli-rt-a"
RUN_B = "cli-rt-b"


def _row(uuid, name, degree, tags):
    return SimulationTable(
        uuid=uuid,
        name=name,
        date="2026-06-01-10:00:00",
        started_at="2026-06-01T10:00:00+01:00",
        parameters={"degree": degree},
        results={"coef": "coef"},
        meta_data={},
        tag=tags,
        note=[],
        runtime="0:00:01",
        status="SUCCESS",
        platform="python",
        hostname="cli-host",
        organisation="",
        author="t",
        project="CLI",
        hashes={},
        sillonversion="2.1.0",
    )


def _make_project(path, rows):
    sillon = path / ".sillon"
    sillon.mkdir(parents=True, exist_ok=True)
    (sillon / "config.toml").write_text(
        '[Environment]\nproject_id = "cli-1"\nproject_name = "CLI"\n'
        '\n[storage]\nstorage_root = ".sillon"\n'
    )
    for uuid, *_ in rows:
        glob_dir = sillon / "glob" / uuid
        glob_dir.mkdir(parents=True, exist_ok=True)
        with h5py.File(glob_dir / "glob.hdf5", "w") as g:
            g.create_dataset("result/coef", data=np.array([1.0, 2.0]))

    engine = create_engine(sqlite_url(sillon / "database.sql"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for uuid, name, degree, tags in rows:
            session.add(_row(uuid, name, degree, tags))
        session.commit()
    engine.dispose()
    return path


@pytest.fixture()
def origin(tmp_path):
    return _make_project(
        tmp_path / "origin",
        [(RUN_A, "deg3", 3, ["sweep"]), (RUN_B, "deg4", 4, ["probe"])],
    )


@pytest.fixture()
def dest(tmp_path):
    return _make_project(tmp_path / "dest", [])


def _export(project, **args):
    defaults = {
        "run_name": None, "dest": None, "no_data": False,
        "parameter": None, "metadata": None, "tag": None,
        "status": None, "before": None, "after": None,
    }
    defaults.update(args)
    import os

    cwd = os.getcwd()
    os.chdir(project)  # the handler takes the project root from cwd
    try:
        return export.command(
            resolve_engine(project), resolve_storage_root(project), defaults
        )
    finally:
        os.chdir(cwd)


def _import(project, source, **args):
    defaults = {
        "source": str(source), "dry_run": False, "no_data": False,
        "inspect": False, "scan": False,
    }
    defaults.update(args)
    return import_cmd.command(
        resolve_engine(project), resolve_storage_root(project), defaults
    )


# ==========================================
#                  EXPORT
# ==========================================
def test_export_writes_the_whole_project_by_default(origin, tmp_path):
    result = _export(origin, dest=str(tmp_path / "all.sillon"))
    assert sorted(result["runs"]) == ["deg3", "deg4"]
    assert result["path"].exists()


def test_export_by_name(origin, tmp_path):
    result = _export(origin, run_name=["deg3"], dest=str(tmp_path / "one.sillon"))
    assert result["runs"] == ["deg3"]


def test_export_by_tag(origin, tmp_path):
    result = _export(origin, tag=["sweep"], dest=str(tmp_path / "t.sillon"))
    assert result["runs"] == ["deg3"]


def test_export_by_parameter_parses_the_value_as_a_literal(origin, tmp_path):
    """`-p degree=4` must compare as an int, not the string "4"."""
    result = _export(origin, parameter=["degree=4"], dest=str(tmp_path / "p.sillon"))
    assert result["runs"] == ["deg4"]


def test_export_by_status(origin, tmp_path):
    assert len(_export(origin, status="SUCCESS", dest=str(tmp_path / "s.sillon"))["runs"]) == 2
    assert _export(origin, status="CRASHED", dest=str(tmp_path / "c.sillon")) is None


def test_export_dest_can_be_a_directory(origin, tmp_path):
    folder = tmp_path / "outbox"
    folder.mkdir()
    result = _export(origin, dest=str(folder))
    assert result["path"].parent == folder
    assert result["path"].suffix == ".sillon"


def test_export_no_data(origin, tmp_path):
    result = _export(origin, no_data=True, dest=str(tmp_path / "light.sillon"))
    assert result["with_data"] is False


def test_export_with_no_match_reports_instead_of_raising(origin, tmp_path):
    assert _export(origin, tag=["nothing"], dest=str(tmp_path / "x.sillon")) is None


# ==========================================
#                  IMPORT
# ==========================================
def test_import_adds_the_runs(origin, dest, tmp_path):
    bundle = _export(origin, dest=str(tmp_path / "b.sillon"))["path"]
    result = _import(dest, bundle)
    assert result["imported"] == 2
    assert result["files_copied"] > 0


def test_import_dry_run_changes_nothing(origin, dest, tmp_path):
    from silloncommon.database import select_run_index

    bundle = _export(origin, dest=str(tmp_path / "b.sillon"))["path"]
    result = _import(dest, bundle, dry_run=True)
    assert result["dry_run"] is True
    assert len(result["new"]) == 2
    assert select_run_index(resolve_engine(dest)) == []


def test_import_no_data_skips_the_copy(origin, dest, tmp_path):
    bundle = _export(origin, dest=str(tmp_path / "b.sillon"))["path"]
    result = _import(dest, bundle, no_data=True)
    assert result["imported"] == 2
    assert result["files_copied"] == 0


def test_import_inspect_describes_without_importing(origin, dest, tmp_path):
    from silloncommon.database import select_run_index

    bundle = _export(origin, dest=str(tmp_path / "b.sillon"))["path"]
    described = _import(dest, bundle, inspect=True)
    assert described["run_count"] == 2
    assert described["project_name"] == "CLI"
    assert select_run_index(resolve_engine(dest)) == []


def test_import_of_a_missing_file_reports_instead_of_raising(dest, tmp_path):
    assert _import(dest, tmp_path / "nope.sillon") is None


def test_import_of_a_non_bundle_reports_instead_of_raising(dest, tmp_path):
    junk = tmp_path / "junk.sillon"
    junk.write_text("not a zip")
    assert _import(dest, junk) is None


def test_the_round_trip_through_both_commands(origin, dest, tmp_path):
    from silloncommon.database import select_run_index

    bundle = _export(origin, dest=str(tmp_path / "rt.sillon"))["path"]
    _import(dest, bundle)
    arrived = {e["name"]: e for e in select_run_index(resolve_engine(dest))}
    assert set(arrived) == {"deg3", "deg4"}
    assert arrived["deg3"]["uuid"] == RUN_A
    assert arrived["deg3"]["sillonversion"] == "2.1.0"


# ==========================================
#              IMPORT --scan
# ==========================================
def test_import_scan_walks_a_tree(tmp_path, dest):
    from silloncommon.database import select_run_index

    tree = tmp_path / "tree"
    _make_project(tree / "alpha", [(RUN_A, "deg3", 3, [])])
    _make_project(tree / "sub" / "beta", [(RUN_B, "deg4", 4, [])])

    result = _import(dest, tree, scan=True)
    assert result["imported"] == 2
    assert len(result["sources"]) == 2
    assert {e["name"] for e in select_run_index(resolve_engine(dest))} == {"deg3", "deg4"}


def test_import_scan_dry_run(tmp_path, dest):
    from silloncommon.database import select_run_index

    tree = tmp_path / "tree"
    _make_project(tree / "alpha", [(RUN_A, "deg3", 3, [])])

    result = _import(dest, tree, scan=True, dry_run=True)
    assert result["dry_run"] is True
    assert result["imported"] == 1
    assert select_run_index(resolve_engine(dest)) == []


def test_import_scan_of_an_empty_tree_reports_instead_of_raising(tmp_path, dest):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _import(dest, empty, scan=True) is None


def test_scan_and_inspect_together_are_refused(tmp_path, dest):
    """They answer different questions; silently picking one would mislead."""
    tree = tmp_path / "tree"
    _make_project(tree / "alpha", [(RUN_A, "deg3", 3, [])])
    assert _import(dest, tree, scan=True, inspect=True) is None


def test_import_of_a_project_directory(tmp_path, dest):
    from silloncommon.database import select_run_index

    origin = _make_project(tmp_path / "origin2", [(RUN_A, "deg3", 3, [])])
    result = _import(dest, origin)
    assert result["imported"] == 1
    assert result["source"]["kind"] == "project"
    assert {e["name"] for e in select_run_index(resolve_engine(dest))} == {"deg3"}


def test_import_of_a_plain_directory_reports_instead_of_raising(tmp_path, dest):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _import(dest, plain) is None
