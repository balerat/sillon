"""Merging a tree of real projects, the way one actually accumulates.

Not one tidy project per topic — a few years of projects created wherever the
script happened to be, at whatever depth, some sharing run names because they
were all sweeps over `degree`. This drives the real client and daemon so the
projects are built the way sillon builds them, then merges the lot into one.
"""

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

CURRENT_PATH = Path(__file__).parent.resolve()
# Cryptically short on purpose: an AF_UNIX socket path is capped around 104
# bytes, and this directory is already 60 of them. `_sm/a/b/c/g/.sillon/
# daemon.sock` fits; spelling the names out does not. Depth at greater remove
# is covered by `find_projects` in the core tests, which needs no daemon.
TREE = CURRENT_PATH / "_sm"
DEST = CURRENT_PATH / "_sd"

SCRIPT = textwrap.dedent(
    """
    import sys
    import numpy as np
    import sillonpy as sp

    with sp.track_run(run_name=sys.argv[1], project_name=sys.argv[2],
                      author="d", project_path="."):
        sp.log_param("degree", int(sys.argv[3]))
        sp.log_result("field", np.arange(128, dtype="float64") * int(sys.argv[3]))
    """
)


def _log(project: Path, run_name: str, project_name: str, degree: int):
    project.mkdir(parents=True, exist_ok=True)
    (project / "run.py").write_text(SCRIPT)
    proc = subprocess.run(
        [sys.executable, "run.py", run_name, project_name, str(degree)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "SILLON_IDLE_TIMEOUT": "2.0"},
    )
    assert proc.returncode == 0, proc.stderr


@pytest.fixture(scope="module")
def tree():
    for path in (TREE, DEST):
        shutil.rmtree(path, ignore_errors=True)

    # Three projects at three depths, two of them using the name `deg3`.
    _log(TREE / "al", "deg3", "Alpha", 3)
    _log(TREE / "al", "deg5", "Alpha", 5)
    _log(TREE / "n" / "be", "deg3", "Beta", 33)
    _log(TREE / "a" / "b" / "c" / "ga", "deg7", "Gamma", 7)

    # And a destination that already has its own `deg3`.
    _log(DEST, "deg3", "Destination", 99)

    yield
    for path in (TREE, DEST):
        shutil.rmtree(path, ignore_errors=True)


def _dest():
    import sillonlab as sl

    return sl.load_project(DEST)


@pytest.fixture(scope="module")
def merged(tree):
    return _dest().import_tree(TREE)


def test_the_dry_run_matches_what_happens(tree):
    """Run first, so this sees the pre-merge state."""
    plan = _dest().import_tree(TREE, dry_run=True)
    assert plan["dry_run"] is True
    assert plan["imported"] == 4
    assert len(plan["sources"]) == 3
    # Nothing moved.
    assert {r.name for r in _dest().runs()} == {"deg3"}


def test_every_project_in_the_tree_is_found(merged):
    assert {s["source"]["project_name"] for s in merged["sources"]} == {
        "Alpha", "Beta", "Gamma",
    }


def test_all_four_runs_arrive(merged):
    assert merged["imported"] == 4
    assert len(_dest().runs()) == 5


def test_colliding_names_are_tagged_with_their_project(merged):
    """All on one machine, so the hostname would distinguish nothing."""
    names = {r.name for r in _dest().runs()}
    assert names == {"deg3", "deg3~Alpha", "deg3~Beta", "deg5", "deg7"}


def test_each_run_keeps_its_own_values(merged):
    project = _dest()
    assert project.get("deg3").parameters["degree"] == 99       # local
    assert project.get("deg3~Alpha").parameters["degree"] == 3
    assert project.get("deg3~Beta").parameters["degree"] == 33


def test_the_heavy_data_came_with_them(merged):
    import numpy as np

    field = _dest().get("deg3~Beta").load_result("field")
    assert np.array_equal(field, np.arange(128, dtype="float64") * 33)


def test_the_source_projects_are_untouched(merged):
    import sillonlab as sl

    alpha = sl.load_project(TREE / "al")
    assert {r.name for r in alpha.runs()} == {"deg3", "deg5"}
    assert alpha.get("deg3").parameters["degree"] == 3


def test_scanning_again_adds_nothing(merged):
    again = _dest().import_tree(TREE)
    assert again["imported"] == 0
    assert again["skipped"] == 4
    assert len(_dest().runs()) == 5


def test_the_destination_is_not_scanned_into_itself(tree):
    """A project sitting inside the tree it is told to scan."""
    inside = TREE / "in"
    _log(inside, "own", "Inside", 1)
    import sillonlab as sl

    result = sl.load_project(inside).import_tree(TREE)
    assert "Inside" not in {s["source"]["project_name"] for s in result["sources"]}
    assert "own" in {r.name for r in sl.load_project(inside).runs()}
    shutil.rmtree(inside, ignore_errors=True)
