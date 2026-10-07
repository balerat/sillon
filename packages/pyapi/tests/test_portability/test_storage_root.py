"""Where a run's data lands, through the real daemon.

Two things used to be true at once: the daemon honoured
`[storage].storage_root` from `config.toml`, and that value was written as an
**absolute** path. So a project that moved kept working for readers — they
ignored the setting — while the next run the daemon logged wrote its glob and
artifacts back to the *old* path, recreating a directory outside the project
you were standing in.

Nothing caught it because the writer and the reader only disagree when the
project is not where it was, and no test ever moved one.
"""

import os
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from silloncommon import project_config
from silloncommon.socket_path import get_pidfile_path

CURRENT_PATH = Path(__file__).parent.resolve()

# Short paths: an AF_UNIX socket path is capped around 104 bytes, and a
# pytest tmp_path is already most of that.
HOME = CURRENT_PATH / "_moved"
AWAY = CURRENT_PATH / "_moved_elsewhere"
# A path the stale-root test points a config at; it must not exist, or the
# root is not stale any more and there is nothing to heal.
GONE = CURRENT_PATH / "_gone"

IDLE = 2.0  # so the daemon is gone before we move its project out from under it

RUN_SCRIPT = textwrap.dedent(
    """
    import sys
    import numpy as np
    import sillonpy as sp

    with sp.track_run(run_name=sys.argv[1], author="t", project_name="moved",
                      project_path="."):
        sp.log_param("degree", int(sys.argv[2]))
        sp.log_result("field", np.arange(64, dtype="float64"))
    """
)


def _log_run(project: Path, name: str, degree: int, script: str = RUN_SCRIPT):
    """Run a real script in `project`, from inside it, and wait for the daemon."""
    (project / "run.py").write_text(script)
    proc = subprocess.run(
        [sys.executable, "run.py", name, str(degree)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=90,
        env={**os.environ, "SILLON_IDLE_TIMEOUT": str(IDLE)},
    )
    assert proc.returncode == 0, proc.stderr
    _wait_for_daemon_to_go(project)


def _wait_for_daemon_to_go(project: Path):
    """A project cannot be moved while its daemon is serving it.

    Daemon endpoint files are process-local and must never travel with a
    project — a moved AF_UNIX socket keeps its inode, so connecting to it
    would reach the old daemon, still holding the old path.

    Watched through the pidfile rather than by connecting: a probe connection
    counts as activity and resets the idle timer, so polling the socket keeps
    the daemon alive forever.
    """
    pid_file = get_pidfile_path(str(project))
    try:
        pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return  # no daemon was recorded; nothing to wait for

    deadline = time.monotonic() + IDLE + 25
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.25)
    pytest.fail(f"daemon {pid} for {project} never exited")


def _runs(project: Path):
    import sillonlab as sl

    return {run.name: run for run in sl.load_project(project).runs()}


@pytest.fixture(autouse=True)
def clean():
    for path in (HOME, AWAY, GONE):
        shutil.rmtree(path, ignore_errors=True)
    HOME.mkdir(parents=True)
    yield
    for path in (HOME, AWAY, GONE):
        shutil.rmtree(path, ignore_errors=True)


# ==========================================
#            THE DEFAULT LAYOUT
# ==========================================
def test_a_run_lands_under_dot_sillon(clean):
    _log_run(HOME, "deg3", 3)
    assert (HOME / ".sillon" / "database.sql").exists()
    globs = list((HOME / ".sillon" / "glob").iterdir())
    assert len(globs) == 1
    assert (globs[0] / "glob.hdf5").exists()


def test_the_recorded_root_is_relative(clean):
    """An absolute value here is what broke on a move."""
    _log_run(HOME, "deg3", 3)
    recorded = project_config.read_config(HOME)["storage"]["storage_root"]
    assert not Path(recorded).is_absolute(), recorded
    assert recorded == ".sillon"


# ==========================================
#              MOVING A PROJECT
# ==========================================
def test_the_next_run_after_a_move_lands_in_the_new_place(clean):
    """The headline bug: data written back to the path the project left."""
    _log_run(HOME, "deg3", 3)
    HOME.rename(AWAY)

    _log_run(AWAY, "deg4", 4)

    # Nothing was recreated where the project used to be.
    assert not HOME.exists(), f"{HOME} was recreated after the move"

    # The second run's data is in the project we are actually standing in.
    globs = sorted(p.name for p in (AWAY / ".sillon" / "glob").iterdir())
    assert len(globs) == 2, globs
    for glob_dir in (AWAY / ".sillon" / "glob").iterdir():
        assert (glob_dir / "glob.hdf5").exists()


def test_both_runs_are_readable_after_a_move(clean):
    _log_run(HOME, "deg3", 3)
    HOME.rename(AWAY)
    _log_run(AWAY, "deg4", 4)

    runs = _runs(AWAY)
    assert set(runs) == {"deg3", "deg4"}
    assert runs["deg3"].parameters["degree"] == 3
    assert runs["deg4"].parameters["degree"] == 4
    # The heavy result of the run logged *before* the move still loads.
    assert len(runs["deg3"].load_result("field")) == 64


def test_the_project_keeps_its_identity_across_a_move(clean):
    """`project_id` is how an import tells "same project, two machines"."""
    _log_run(HOME, "deg3", 3)
    before = project_config.project_id(HOME)
    assert before

    HOME.rename(AWAY)
    _log_run(AWAY, "deg4", 4)

    assert project_config.project_id(AWAY) == before


# ==========================================
#          A ROOT THAT IS NOT THERE
# ==========================================
def test_a_stale_absolute_root_is_healed(clean):
    """What every project written before this change has in its config."""
    _log_run(HOME, "deg3", 3)

    # Put the config back the way the old code wrote it, pointing at a path
    # that no longer exists — exactly the post-move state.
    config = project_config.read_config(HOME)
    config["storage"]["storage_root"] = str(GONE / ".sillon")
    project_config.write_config(HOME, config)

    _log_run(HOME, "deg4", 4)

    # It was rewritten to something that travels, and nothing was created at
    # the dead path.
    assert project_config.read_config(HOME)["storage"]["storage_root"] == ".sillon"
    assert not GONE.exists()
    assert set(_runs(HOME)) == {"deg3", "deg4"}


# ==========================================
#           SOURCES FOLLOW THE DATA
# ==========================================
def test_sources_are_stored_under_the_storage_root(clean):
    """The source store moved from "beside the project" to "with the data"."""
    _log_run(HOME, "deg3", 3)
    blobs = list((HOME / ".sillon" / "sources").iterdir())
    assert blobs, "no source text was stored"
    assert any(b.read_text().startswith("\nimport sys") for b in blobs)


def test_a_source_diff_still_works_after_a_move(clean):
    """The source store moved from beside the project to inside the storage root.

    In the default layout both spellings land on `.sillon/sources`, so this
    passes either way today — it is here to catch the custom-storage-root case
    the moment `init --storage-root` makes one reachable, and to pin that a
    diff reads its text through the storage root.
    """
    import sillonlab as sl

    _log_run(HOME, "deg3", 3)
    # A genuinely different script, so there is something to diff.
    _log_run(HOME, "deg4", 4, script=RUN_SCRIPT.replace("degree", "order"))
    HOME.rename(AWAY)

    # The source diff is always computed; `--source` only decides whether the
    # CLI prints it.
    result = sl.load_project(AWAY).diff("deg3", "deg4")
    assert result["code"]["source_diff"], "no source diff was produced"
    assert "order" in result["code"]["source_diff"]
