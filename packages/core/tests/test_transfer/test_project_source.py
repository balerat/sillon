"""Importing from another project, with no packing step in between.

Crossing a machine boundary needs a bundle. Merging two projects that are both
sitting on this disk does not, and making you export one first would be a
ceremony with no purpose.

`--scan` is the other half: a history of projects created wherever the script
happened to be, which is what you actually have after a few years rather than
one tidy project per topic.
"""

import h5py
import numpy as np
import pytest
from sqlmodel import Session, SQLModel, create_engine

from silloncommon.database import SimulationTable, select_run_index, sqlite_url
from silloncore.bundle import BundleError
from silloncore.engine import import_from, scan_and_import
from silloncore.project_paths import resolve_engine, resolve_storage_root
from silloncore.transfer import ProjectSource, find_projects, open_source


def _row(uuid, name, degree, parents=None, host="somehost"):
    return SimulationTable(
        uuid=uuid,
        name=name,
        date="2026-06-01-10:00:00",
        started_at="2026-06-01T10:00:00+01:00",
        parameters={"degree": degree},
        results={"field": "field"},
        meta_data={},
        tag=["sweep"],
        note=[],
        parents=parents or [],
        runtime="0:00:01",
        status="SUCCESS",
        platform="python",
        hostname=host,
        organisation="",
        author="t",
        project="p",
        hashes={},
        sillonversion="2.1.0",
    )


def _project(path, name, rows, *, with_data=True, storage_root=None):
    """A project on disk, optionally with its data on a different root."""
    sillon = path / ".sillon"
    sillon.mkdir(parents=True, exist_ok=True)
    root = storage_root or sillon
    root.mkdir(parents=True, exist_ok=True)
    recorded = (
        root.relative_to(path).as_posix() if root.is_relative_to(path) else str(root)
    )
    (sillon / "config.toml").write_text(
        f'[Environment]\nproject_id = "{name}-id"\nproject_name = "{name}"\n'
        f'\n[storage]\nstorage_root = "{recorded}"\n'
    )

    uuids = [row.uuid for row in rows]
    engine = create_engine(sqlite_url(root / "database.sql"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for row in rows:
            session.add(row)
        session.commit()
    engine.dispose()

    if with_data:
        for uuid in uuids:
            glob_dir = root / "glob" / uuid
            glob_dir.mkdir(parents=True, exist_ok=True)
            with h5py.File(glob_dir / "glob.hdf5", "w") as g:
                g.create_dataset("result/field", data=np.arange(16, dtype="float64"))
        sources = root / "sources"
        sources.mkdir(parents=True, exist_ok=True)
        (sources / f"{name}hash").write_text(f"# {name}")
    return path


@pytest.fixture()
def dest(tmp_path):
    path = _project(tmp_path / "dest", "Dest", [_row("dest-1", "shared", 99)])
    return {
        "path": path,
        "engine": resolve_engine(path),
        "storage": resolve_storage_root(path),
    }


# ==========================================
#              A PROJECT AS A SOURCE
# ==========================================
def test_a_project_directory_can_be_imported_directly(tmp_path, dest):
    origin = _project(tmp_path / "origin", "Origin", [_row("o-1", "deg3", 3)])
    result = import_from(dest["engine"], dest["storage"], origin)

    assert result["imported"] == 1
    assert result["source"]["kind"] == "project"
    assert result["source"]["project_name"] == "Origin"
    rows = {e["name"]: e for e in select_run_index(dest["engine"])}
    assert rows["deg3"]["uuid"] == "o-1"
    assert rows["deg3"]["sillonversion"] == "2.1.0"


def test_the_data_and_sources_come_across(tmp_path, dest):
    origin = _project(tmp_path / "origin", "Origin", [_row("o-1", "deg3", 3)])
    import_from(dest["engine"], dest["storage"], origin)

    glob = dest["storage"] / "glob" / "o-1" / "glob.hdf5"
    with h5py.File(glob, "r") as g:
        assert np.array_equal(g["result/field"][()], np.arange(16, dtype="float64"))
    assert (dest["storage"] / "sources" / "Originhash").read_text() == "# Origin"


def test_a_collision_is_tagged_with_the_project_not_the_machine(tmp_path, dest):
    """Both projects are on this machine, so the hostname distinguishes nothing."""
    origin = _project(tmp_path / "origin", "Alpha", [_row("o-1", "shared", 7)])
    result = import_from(dest["engine"], dest["storage"], origin)

    assert result["renamed"] == [{"uuid": "o-1", "from": "shared", "to": "shared~Alpha"}]
    rows = {e["name"]: e for e in select_run_index(dest["engine"])}
    assert rows["shared"]["parameters"]["degree"] == 99       # local, untouched
    assert rows["shared~Alpha"]["parameters"]["degree"] == 7


def test_importing_the_same_project_twice_adds_nothing(tmp_path, dest):
    origin = _project(tmp_path / "origin", "Origin", [_row("o-1", "deg3", 3)])
    first = import_from(dest["engine"], dest["storage"], origin)
    second = import_from(dest["engine"], dest["storage"], origin)
    assert (first["imported"], second["imported"]) == (1, 0)
    assert len(select_run_index(dest["engine"])) == 2


def test_a_dry_run_against_a_project_changes_nothing(tmp_path, dest):
    origin = _project(tmp_path / "origin", "Origin", [_row("o-1", "deg3", 3)])
    plan = import_from(dest["engine"], dest["storage"], origin, dry_run=True)
    assert len(plan["new"]) == 1
    assert {e["name"] for e in select_run_index(dest["engine"])} == {"shared"}


def test_a_divergent_storage_root_is_followed(tmp_path, dest):
    """The layout from when a project's data ended up beside it, not under it."""
    origin_path = tmp_path / "origin"
    origin = _project(
        origin_path, "Legacy", [_row("o-1", "deg3", 3)],
        storage_root=tmp_path / "elsewhere" / "store",
    )
    result = import_from(dest["engine"], dest["storage"], origin)

    assert result["imported"] == 1
    with h5py.File(dest["storage"] / "glob" / "o-1" / "glob.hdf5", "r") as g:
        assert g["result/field"].shape == (16,)


def test_lineage_within_the_source_survives(tmp_path, dest):
    import sillonlab as sl

    origin = _project(
        tmp_path / "origin", "Alpha",
        [
            _row("o-1", "shared", 7),
            _row("o-2", "child", 8, parents=[{"uuid": "o-1", "name": "shared"}]),
        ],
    )
    import_from(dest["engine"], dest["storage"], origin)

    parent = sl.load_project(dest["path"]).get("child").parents()[0]
    assert parent.uuid == "o-1"
    assert parent.name == "shared~Alpha"
    assert parent.parameters["degree"] == 7  # not the destination's 99


# ==========================================
#                 BAD SOURCES
# ==========================================
def test_a_directory_that_is_not_a_project(tmp_path):
    plain = tmp_path / "just-a-folder"
    plain.mkdir()
    with pytest.raises(BundleError, match="not a sillon project"):
        open_source(plain)


def test_the_error_points_at_scan(tmp_path):
    """The natural mistake is handing it the tree instead of a project."""
    plain = tmp_path / "tree"
    plain.mkdir()
    with pytest.raises(BundleError, match="--scan"):
        open_source(plain)


def test_a_project_with_no_database(tmp_path):
    broken = tmp_path / "broken"
    (broken / ".sillon").mkdir(parents=True)
    with pytest.raises(BundleError, match="no sillon database"):
        ProjectSource(broken)


def test_a_path_that_does_not_exist(tmp_path):
    with pytest.raises(BundleError, match="No such bundle or project"):
        open_source(tmp_path / "nowhere")


# ==========================================
#              FINDING PROJECTS
# ==========================================
def test_projects_are_found_at_any_depth(tmp_path):
    _project(tmp_path / "tree" / "alpha", "Alpha", [])
    _project(tmp_path / "tree" / "sub" / "beta", "Beta", [])
    _project(tmp_path / "tree" / "deep" / "er" / "gamma", "Gamma", [])

    found = find_projects(tmp_path / "tree")
    assert {p.name for p in found} == {"alpha", "beta", "gamma"}


def test_the_root_itself_counts_as_a_project(tmp_path):
    _project(tmp_path / "tree", "Root", [])
    assert find_projects(tmp_path / "tree") == [(tmp_path / "tree").resolve()]


def test_a_project_inside_a_project_is_not_a_second_project(tmp_path):
    """`.sillon/` holds arbitrary trees; sillon never nests projects."""
    outer = _project(tmp_path / "tree" / "outer", "Outer", [])
    # Something that looks like a project, inside the outer one's data.
    nested = outer / ".sillon" / "glob" / "whatever"
    (nested / ".sillon").mkdir(parents=True)

    found = find_projects(tmp_path / "tree")
    assert found == [outer.resolve()]


def test_the_destination_is_left_out_of_its_own_scan(tmp_path):
    _project(tmp_path / "tree" / "alpha", "Alpha", [])
    me = _project(tmp_path / "tree" / "mine", "Mine", [])

    found = find_projects(tmp_path / "tree", skip=[me])
    assert [p.name for p in found] == ["alpha"]


def test_an_empty_tree(tmp_path):
    (tmp_path / "tree").mkdir()
    assert find_projects(tmp_path / "tree") == []


# ==========================================
#                   SCAN
# ==========================================
def test_scan_imports_every_project_in_the_tree(tmp_path, dest):
    tree = tmp_path / "tree"
    _project(tree / "alpha", "Alpha", [_row("a-1", "deg2", 2), _row("a-2", "shared", 7)])
    _project(tree / "sub" / "beta", "Beta", [_row("b-1", "deg3", 3)])
    _project(tree / "legacy", "Legacy", [_row("c-1", "deg4", 4)])

    result = scan_and_import(
        dest["engine"], dest["storage"], dest["path"], tree
    )

    assert result["imported"] == 4
    assert len(result["sources"]) == 3
    names = {e["name"] for e in select_run_index(dest["engine"])}
    assert names == {"shared", "deg2", "shared~Alpha", "deg3", "deg4"}


def test_a_scan_dry_run_counts_the_same_thing_it_would_do(tmp_path, dest):
    """The summary and the per-project rows must not disagree."""
    tree = tmp_path / "tree"
    _project(tree / "alpha", "Alpha", [_row("a-1", "deg2", 2)])
    _project(tree / "beta", "Beta", [_row("b-1", "deg3", 3)])

    plan = scan_and_import(
        dest["engine"], dest["storage"], dest["path"], tree, dry_run=True
    )
    assert plan["dry_run"] is True
    assert plan["imported"] == 2
    assert sum(len(s["new"]) for s in plan["sources"]) == 2
    assert {e["name"] for e in select_run_index(dest["engine"])} == {"shared"}


def test_scan_skips_the_destination_when_it_is_in_the_tree(tmp_path):
    tree = tmp_path / "tree"
    me = _project(tree / "mine", "Mine", [_row("m-1", "local", 1)])
    _project(tree / "other", "Other", [_row("o-1", "deg3", 3)])
    engine = resolve_engine(me)

    result = scan_and_import(engine, resolve_storage_root(me), me, tree)

    assert [s["source"]["project_name"] for s in result["sources"]] == ["Other"]
    assert {e["name"] for e in select_run_index(engine)} == {"local", "deg3"}


def test_one_unreadable_project_does_not_stop_the_rest(tmp_path, dest):
    tree = tmp_path / "tree"
    _project(tree / "good", "Good", [_row("g-1", "deg3", 3)])
    (tree / "broken" / ".sillon").mkdir(parents=True)  # no database

    result = scan_and_import(dest["engine"], dest["storage"], dest["path"], tree)

    assert result["imported"] == 1
    errors = [s for s in result["sources"] if s.get("error")]
    assert len(errors) == 1
    assert "no sillon database" in errors[0]["error"]


def test_scanning_a_tree_with_nothing_in_it(tmp_path, dest):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(BundleError, match="No sillon projects"):
        scan_and_import(dest["engine"], dest["storage"], dest["path"], empty)


def test_scanning_twice_adds_nothing(tmp_path, dest):
    tree = tmp_path / "tree"
    _project(tree / "alpha", "Alpha", [_row("a-1", "deg2", 2)])

    first = scan_and_import(dest["engine"], dest["storage"], dest["path"], tree)
    second = scan_and_import(dest["engine"], dest["storage"], dest["path"], tree)
    assert (first["imported"], second["imported"]) == (1, 0)
    assert second["skipped"] == 1
