"""Deriving from an earlier run must be recorded without being declared.

The pattern this exists for: load a previous run's result through sillonlab,
compute with it, log a new run. That is a derivation, and sillon already
watched it happen — so no `inherit=` should be needed.

Equally important is what must *not* happen: browsing a project is not
deriving from it, and a long exploratory session must not glue itself onto the
next run you log.
"""

import json
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

CURRENT_PATH = Path(__file__).parent.resolve()
PROJECT = CURRENT_PATH / "_lineage_project"


def _script(body: str) -> str:
    return textwrap.dedent(body).replace("{PROJECT}", str(PROJECT))


def _run(name: str, body: str):
    path = PROJECT / f"_{name}.py"
    path.write_text(_script(body))
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(PROJECT), capture_output=True, text=True, timeout=90,
        )
        assert proc.returncode == 0, proc.stderr
        return proc
    finally:
        path.unlink(missing_ok=True)


def _parents():
    con = sqlite3.connect(PROJECT / ".sillon" / "database.sql")
    try:
        return {
            name: json.loads(parents or "[]")
            for name, parents in con.execute("SELECT name, parents FROM simulationtable")
        }
    finally:
        con.close()


@pytest.fixture(scope="module", autouse=True)
def project():
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    PROJECT.mkdir(parents=True)

    # the run everything else derives from
    _run("seed", """
        import numpy as np, sillonpy as sp
        with sp.track_run(run_name="equilibrated", author="t", project_name="lin",
                          project_path=r"{PROJECT}"):
            sp.log_param("steps", 1000)
            sp.log_result("final_state", np.arange(50, dtype=float))
            sp.log_result("energy", 1.25)
    """)
    time.sleep(0.6)
    yield
    time.sleep(0.3)
    if PROJECT.exists():
        shutil.rmtree(PROJECT, ignore_errors=True)


# ==========================================
#          the edge gets recorded
# ==========================================


def test_loading_a_result_records_a_parent():
    _run("derive", """
        import sillonlab as sl, sillonpy as sp
        state = sl.load_project(r"{PROJECT}").get("equilibrated").load_result("final_state")
        with sp.track_run(run_name="dynamics", author="t", project_name="lin",
                          project_path=r"{PROJECT}"):
            sp.log_result("trajectory", state * 2)
    """)
    time.sleep(0.6)

    parents = _parents()["dynamics"]
    assert len(parents) == 1
    assert parents[0]["name"] == "equilibrated"
    assert parents[0]["relation"] == "read"
    assert parents[0]["items"] == ["final_state"]


def test_every_item_read_is_named():
    _run("two_items", """
        import sillonlab as sl, sillonpy as sp
        run = sl.load_project(r"{PROJECT}").get("equilibrated")
        run.load_result("final_state")
        run.load_result("energy")
        run.load_parameter("steps")
        with sp.track_run(run_name="multi", author="t", project_name="lin",
                          project_path=r"{PROJECT}"):
            sp.log_param("x", 1)
    """)
    time.sleep(0.6)

    parents = _parents()["multi"]
    assert len(parents) == 1, "one parent, not one per item"
    assert parents[0]["items"] == ["energy", "final_state", "steps"]


def test_reads_before_init_are_still_captured():
    """The usual order: load the previous result, *then* start the new run."""
    parents = _parents()["dynamics"]
    assert parents and parents[0]["name"] == "equilibrated"


# ==========================================
#        what must NOT create an edge
# ==========================================


def test_browsing_a_project_records_nothing():
    """Looking at a run is not deriving from it."""
    _run("browse", """
        import sillonlab as sl, sillonpy as sp
        project = sl.load_project(r"{PROJECT}")
        for run in project.runs():
            _ = run.name, run.parameters, run.status, run.tags, run.results
        project.runs().show()
        with sp.track_run(run_name="after_browsing", author="t", project_name="lin",
                          project_path=r"{PROJECT}"):
            sp.log_param("x", 1)
    """)
    time.sleep(0.6)
    assert _parents()["after_browsing"] == []


def test_forget_reads_clears_the_pending_edges():
    _run("forget", """
        import sillonlab as sl, sillonpy as sp
        sl.load_project(r"{PROJECT}").get("equilibrated").load_result("final_state")
        assert len(sl.pending_reads()) == 1
        sl.forget_reads()
        assert sl.pending_reads() == []
        with sp.track_run(run_name="after_forget", author="t", project_name="lin",
                          project_path=r"{PROJECT}"):
            sp.log_param("x", 1)
    """)
    time.sleep(0.6)
    assert _parents()["after_forget"] == []


def test_reading_your_own_run_is_not_self_lineage():
    _run("self", """
        import sillonlab as sl, sillonpy as sp
        with sp.track_run(run_name="selfread", author="t", project_name="lin",
                          project_path=r"{PROJECT}"):
            sp.log_result("value", 42)
        sl.load_project(r"{PROJECT}").get("selfread").load_result("value")
    """)
    time.sleep(0.6)
    assert _parents()["selfread"] == []


def test_the_log_clears_between_runs():
    """A read feeding run A must not also attach itself to run B."""
    _run("sequential", """
        import sillonlab as sl, sillonpy as sp
        sl.load_project(r"{PROJECT}").get("equilibrated").load_result("final_state")
        with sp.track_run(run_name="first", author="t", project_name="lin",
                          project_path=r"{PROJECT}"):
            sp.log_param("x", 1)
        with sp.track_run(run_name="second", author="t", project_name="lin",
                          project_path=r"{PROJECT}"):
            sp.log_param("x", 2)
    """)
    time.sleep(0.8)

    parents = _parents()
    assert len(parents["first"]) == 1
    assert parents["second"] == [], "the read leaked into the following run"


# ==========================================
#        explicit and automatic together
# ==========================================


def test_an_explicit_inherit_is_labelled_differently():
    _run("explicit", """
        import sillonpy as sp
        with sp.track_run(run_name="declared", author="t", project_name="lin",
                          project_path=r"{PROJECT}", inherit="equilibrated"):
            sp.log_param("x", 1)
    """)
    time.sleep(0.6)

    parents = _parents()["declared"]
    assert len(parents) == 1
    assert parents[0]["relation"] == "derived-from"


def test_inherit_and_read_of_the_same_run_merge_into_one_edge():
    _run("both", """
        import sillonlab as sl, sillonpy as sp
        sl.load_project(r"{PROJECT}").get("equilibrated").load_result("final_state")
        with sp.track_run(run_name="both_ways", author="t", project_name="lin",
                          project_path=r"{PROJECT}", inherit="equilibrated"):
            sp.log_param("x", 1)
    """)
    time.sleep(0.6)

    parents = _parents()["both_ways"]
    assert len(parents) == 1, "the same parent was recorded twice"
    # the deliberate claim wins, and the read's detail is kept
    assert parents[0]["relation"] == "derived-from"
    assert "final_state" in parents[0]["items"]


# ==========================================
#          reading it back
# ==========================================


def test_lineage_is_navigable_from_sillonlab():
    import sillonlab as sl

    project = sl.load_project(PROJECT)
    child = project.get("dynamics")

    assert [p["name"] for p in child.parent_links()] == ["equilibrated"]
    assert "dynamics" in project.get("equilibrated").children().list()
