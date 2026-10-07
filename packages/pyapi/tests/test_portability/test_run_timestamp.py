"""A real run must record both timestamp forms.

`date` is what people read; `started_at` is what orders runs once more than
one machine has contributed to a project. The unit tests cover the resolver
and the migration — this one checks the daemon actually writes it.
"""

import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import pytest

from silloncommon import timestamps
from silloncommon.database import SCHEMA_VERSION, schema_version
from silloncore.project_paths import resolve_engine

CURRENT_PATH = Path(__file__).parent.resolve()
PROJECT = CURRENT_PATH / "_stamped"

SCRIPT = textwrap.dedent(
    """
    import sillonpy as sp

    with sp.track_run(run_name="stamped", author="t", project_name="stamps",
                      project_path="."):
        sp.log_param("degree", 3)
    """
)


@pytest.fixture(autouse=True)
def project():
    shutil.rmtree(PROJECT, ignore_errors=True)
    PROJECT.mkdir(parents=True)
    (PROJECT / "run.py").write_text(SCRIPT)
    proc = subprocess.run(
        [sys.executable, "run.py"],
        cwd=str(PROJECT),
        capture_output=True,
        text=True,
        timeout=90,
        env={**os.environ, "SILLON_IDLE_TIMEOUT": "2.0"},
    )
    assert proc.returncode == 0, proc.stderr
    yield
    shutil.rmtree(PROJECT, ignore_errors=True)


def _row():
    from silloncommon.database import select_run_index

    index = select_run_index(resolve_engine(PROJECT))
    assert len(index) == 1, index
    return index[0]


def test_both_timestamp_forms_are_written(project):
    row = _row()
    assert row["date"], "no display date"
    assert row["started_at"], "no offset-aware timestamp"


def test_they_describe_the_same_instant(project):
    row = _row()
    naive = datetime.strptime(row["date"], timestamps.DATE_FORMAT)
    aware = datetime.fromisoformat(row["started_at"])
    assert aware.tzinfo is not None, "started_at has no offset"
    assert aware.replace(tzinfo=None) == naive


def test_the_timestamp_is_recent(project):
    """Guards against a stamp inherited from somewhere else entirely."""
    moment = timestamps.to_aware(None, _row()["started_at"])
    age = abs((datetime.now().astimezone() - moment).total_seconds())
    assert age < 300, f"started_at is {age:.0f}s away from now"


def test_a_new_project_records_the_schema_version(project):
    assert schema_version(resolve_engine(PROJECT)) == SCHEMA_VERSION
