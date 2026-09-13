"""A run's recorded status must reflect what actually happened.

Three exit paths, three verdicts:
  * clean exit                 -> SUCCESS
  * uncaught Python exception  -> CRASHED  (atexit still dumps, so the client
                                            must say so; this was the bug)
  * killed process             -> CRASHED  (no dump at all; the daemon infers it
                                            from the disconnect -- already worked,
                                            guarded here against regression)
"""

import shutil
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

CURRENT_PATH = Path(__file__).parent.resolve()
SILLON_PATH = CURRENT_PATH / ".sillon"
DB_PATH = SILLON_PATH / "database.sql"


@pytest.fixture(scope="module", autouse=True)
def clean_workspace():
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH)
    yield
    time.sleep(1)
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH, ignore_errors=True)


def _run_script(body: str):
    """Execute a snippet as a real separate process, like a user's simulation."""
    script = CURRENT_PATH / "_tmp_script.py"
    script.write_text(textwrap.dedent(body))
    try:
        return subprocess.run(
            [sys.executable, str(script)],
            cwd=str(CURRENT_PATH),
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        script.unlink(missing_ok=True)


def _status_of(run_name: str):
    for _ in range(40):  # the daemon commits asynchronously
        if DB_PATH.exists():
            con = sqlite3.connect(DB_PATH)
            try:
                row = con.execute(
                    "SELECT status FROM simulationtable WHERE name = ?", (run_name,)
                ).fetchone()
            finally:
                con.close()
            if row:
                return row[0]
        time.sleep(0.25)
    return None


def test_clean_run_is_success():
    _run_script(
        """
        import sillonpy as sp
        with sp.track_run(run_name="clean_run", author="t", project_name="status"):
            sp.log_param("x", 1)
        """
    )
    assert _status_of("clean_run") == "SUCCESS"


def test_uncaught_exception_is_crashed():
    """The regression: atexit fires on a crash too, so a dump is still sent."""
    proc = _run_script(
        """
        import sillonpy as sp
        with sp.track_run(run_name="raising_run", author="t", project_name="status"):
            sp.log_param("x", 1)
            raise RuntimeError("the simulation blew up")
        """
    )
    assert proc.returncode != 0
    # The user's traceback must still print -- the excepthook chains, not replaces.
    assert "the simulation blew up" in proc.stderr

    assert _status_of("raising_run") == "CRASHED"


def test_uncaught_exception_records_the_cause():
    _run_script(
        """
        import sillonpy as sp
        with sp.track_run(run_name="cause_run", author="t", project_name="status"):
            raise ValueError("bad parameter combination")
        """
    )
    assert _status_of("cause_run") == "CRASHED"

    con = sqlite3.connect(DB_PATH)
    try:
        meta = con.execute(
            "SELECT meta_data FROM simulationtable WHERE name = ?", ("cause_run",)
        ).fetchone()[0]
    finally:
        con.close()
    assert "ValueError" in meta
    assert "bad parameter combination" in meta


def test_killed_process_is_still_crashed():
    """Guard on the path that already worked: no dump, daemon infers from disconnect."""
    _run_script(
        """
        import os, signal, sillonpy as sp
        sp.init(run_name="killed_run", author="t", project_name="status")
        sp.log_param("x", 1)
        os.kill(os.getpid(), signal.SIGKILL)
        """
    )
    assert _status_of("killed_run") == "CRASHED"
