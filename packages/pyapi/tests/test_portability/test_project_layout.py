"""Project layout, with the real client and daemon.

Three things the unit tests can describe but not prove:

- A run logged from a **subdirectory** must land in the project above it, not
  create a second project where the script happens to sit.
- A **custom storage root** must be honoured by the daemon *and* the readers.
  The plumbing existed on both ends and was dead on both: the daemon read the
  setting, the readers had it commented out.
- `sillon init` and the first logged run must produce the **same** project,
  because the daemon still creates one as a side effect and always will.
"""

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from silloncommon import project_config
from silloncore.project_paths import resolve_engine
from silloncore.projects import create_project

CURRENT_PATH = Path(__file__).parent.resolve()
# Short, for the AF_UNIX socket path cap.
PROJ = CURRENT_PATH / "_pl"
BIG = CURRENT_PATH / "_pl_disk"

SCRIPT = textwrap.dedent(
    """
    import sys
    import numpy as np
    import sillonpy as sp

    with sp.track_run(run_name=sys.argv[1], project_name="Layout", author="d",
                      project_path=sys.argv[2]):
        sp.log_param("degree", 3)
        sp.log_result("field", np.arange(64, dtype="float64"))
    """
)


def _log(cwd: Path, run_name: str, project_path: str):
    cwd.mkdir(parents=True, exist_ok=True)
    (cwd / "run.py").write_text(SCRIPT)
    proc = subprocess.run(
        [sys.executable, "run.py", run_name, project_path],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "SILLON_IDLE_TIMEOUT": "2.0"},
    )
    assert proc.returncode == 0, proc.stderr


@pytest.fixture(autouse=True)
def clean():
    for path in (PROJ, BIG):
        shutil.rmtree(path, ignore_errors=True)
    yield
    for path in (PROJ, BIG):
        shutil.rmtree(path, ignore_errors=True)


def _runs(project):
    import sillonlab as sl

    return {run.name: run for run in sl.load_project(project).runs()}


# ==========================================
#          WORKING FROM A SUBDIRECTORY
# ==========================================
def test_a_run_logged_from_a_subdirectory_joins_the_project_above(clean):
    create_project(PROJ, project_name="Layout")
    sub = PROJ / "scripts" / "sweeps"

    # `project_path="."` from a subdirectory: the project is found upward.
    _log(sub, "from_sub", ".")

    assert not (sub / ".sillon").exists(), "a second project was created"
    assert "from_sub" in _runs(PROJ)


def test_sillonlab_opens_the_project_from_a_subdirectory(clean):
    create_project(PROJ, project_name="Layout")
    _log(PROJ, "r1", ".")
    deep = PROJ / "analysis" / "figures"
    deep.mkdir(parents=True)

    import sillonlab as sl

    project = sl.load_project(deep)
    assert project.path == PROJ.resolve()
    assert project.name == "Layout"
    assert "r1" in {r.name for r in project.runs()}


def test_the_cli_works_from_a_subdirectory(clean):
    create_project(PROJ, project_name="Layout")
    _log(PROJ, "r1", ".")
    deep = PROJ / "analysis"
    deep.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [sys.executable, "-m", "silloncli.main", "list"],
        cwd=str(deep), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "r1" in proc.stdout
    # The panel title is the project's name, not the subdirectory's.
    assert "Layout" in proc.stdout


# ==========================================
#            A CUSTOM STORAGE ROOT
# ==========================================
def test_the_daemon_writes_to_a_custom_root_and_readers_find_it(clean):
    external = BIG / "store"
    create_project(PROJ, project_name="Layout", storage_root=external)

    _log(PROJ, "r1", ".")

    # The database and the heavy data are both on the other "disk".
    assert (external / "database.sql").is_file()
    globs = list((external / "glob").iterdir())
    assert len(globs) == 1 and (globs[0] / "glob.hdf5").is_file()
    assert not (PROJ / ".sillon" / "glob").exists()

    # And a reader agrees -- the half that used to be commented out.
    assert project_config.resolve_storage_root(PROJ) == external.resolve()
    assert len(_runs(PROJ)["r1"].load_result("field")) == 64


def test_sources_live_with_the_data_not_beside_the_project(clean):
    external = BIG / "store"
    create_project(PROJ, project_name="Layout", storage_root=external)
    _log(PROJ, "r1", ".")

    assert (external / "sources").is_dir()
    assert list((external / "sources").iterdir())
    assert not (PROJ / ".sillon" / "sources").exists()


def test_a_custom_root_survives_the_project_moving(clean):
    """An external root is absolute by necessity, so it does not travel.

    It must still be honoured where it is, and the runs still readable.
    """
    external = BIG / "store"
    create_project(PROJ, project_name="Layout", storage_root=external)
    _log(PROJ, "r1", ".")

    moved = CURRENT_PATH / "_pl_moved"
    shutil.rmtree(moved, ignore_errors=True)
    PROJ.rename(moved)
    try:
        assert project_config.resolve_storage_root(moved) == external.resolve()
        assert "r1" in {r.name for r in __import__("sillonlab").load_project(moved).runs()}
    finally:
        shutil.rmtree(moved, ignore_errors=True)


# ==========================================
#        init AND THE DAEMON AGREE
# ==========================================
def test_init_then_log_keeps_one_project(clean):
    info = create_project(PROJ, project_name="Layout")
    _log(PROJ, "r1", ".")

    assert project_config.project_id(PROJ) == info["project_id"]
    assert project_config.project_name(PROJ) == "Layout"
    assert len(_runs(PROJ)) == 1


def test_logging_first_produces_the_same_shape_as_init(clean):
    """The daemon's side effect and `init` must not drift apart."""
    _log(PROJ, "r1", ".")
    by_daemon = set(p.name for p in (PROJ / ".sillon").iterdir())

    other = CURRENT_PATH / "_pl_init"
    shutil.rmtree(other, ignore_errors=True)
    try:
        create_project(other, project_name="Layout")
        by_init = set(p.name for p in (other / ".sillon").iterdir())
        # `init` makes no daemon files and no staging dir; everything it does
        # make, the daemon makes too.
        assert by_init <= by_daemon, by_init - by_daemon
        assert {"config.toml", "database.sql"} <= by_init
    finally:
        shutil.rmtree(other, ignore_errors=True)


def test_a_nameless_project_learns_its_name_from_the_first_run(clean):
    """`init` with no name, then a run that has one."""
    create_project(PROJ)
    assert project_config.project_name(PROJ) == ""

    _log(PROJ, "r1", ".")
    assert project_config.project_name(PROJ) == "Layout"
