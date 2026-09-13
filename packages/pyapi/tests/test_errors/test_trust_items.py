"""Phase 7 guards: failures must stay contained and legible.

Each test covers a bug where one failure quietly destroyed data beyond itself,
or where a written-but-unreachable error message left the user with a traceback
from sillon's internals.
"""

import shutil
import time
from pathlib import Path

import numpy as np
import pytest

CURRENT_PATH = Path(__file__).parent.resolve()


# --- get_context ------------------------------------------------------------


def test_logging_before_init_names_the_fix():
    """The RuntimeError existed but was unreachable: a ContextVar with a
    default never raises, so get_context() returned None and every log_* call
    died with "'NoneType' object has no attribute ..." instead."""
    import sillonpy as sp
    from sillonpy.api import set_context

    set_context(None)
    with pytest.raises(RuntimeError) as excinfo:
        sp.log_param("x", 1)

    message = str(excinfo.value)
    assert "init" in message, "the error must name the call the user forgot"
    assert "NoneType" not in message


def test_init_and_finalize_tolerate_no_context():
    """init() and the atexit hook read the context expecting None, so they must
    not go through the raising accessor."""
    from sillonpy.api import _current_context, _finalize, set_context

    set_context(None)
    assert _current_context() is None
    _finalize()  # must not raise when no run was ever started


# --- glob: one bad value must not take the others with it -------------------


@pytest.fixture
def glob(tmp_path):
    from silloncore.glob import Glob

    g = Glob(tmp_path)
    yield g
    try:
        g.close()
    except Exception:
        pass


class _Unwritable:
    """h5py cannot store this."""


def test_one_bad_result_does_not_discard_the_others(glob, tmp_path):
    glob.save("good_before", np.arange(10))
    glob.save("bad", _Unwritable())
    glob.save("good_after", np.arange(10))

    glob.commit_result()

    stored = set(glob.file["result"].keys())
    assert "good_before" in stored
    assert "good_after" in stored, "a later result was dropped by an earlier failure"
    assert "bad" not in stored


def test_one_bad_parameter_does_not_discard_the_others(glob, tmp_path):
    """commit_parameter wrapped the whole loop, so this used to lose
    'good_after' and skip the flush entirely."""
    glob.save_param("good_before", np.arange(10))
    glob.save_param("bad", _Unwritable())
    glob.save_param("good_after", np.arange(10))

    glob.commit_parameter()

    stored = set(glob.file["parameter"].keys())
    assert "good_before" in stored
    assert "good_after" in stored, "a later parameter was dropped by an earlier failure"
    assert "bad" not in stored


# --- session rollback -------------------------------------------------------


def test_failed_commit_does_not_poison_later_runs(tmp_path, monkeypatch):
    """One Session serves the daemon's whole life. Without a rollback, a single
    failed commit leaves it in a failed transaction and every *subsequent* run
    raises PendingRollbackError -- silent, cascading data loss.

    The failure is induced the way it really happens: a value the JSON column
    cannot serialize (a complex number in metadata) blows up during flush.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import PendingRollbackError

    import silloncore.envhandler as envhandler_module
    from silloncore.envhandler import ProjectEnvironmentHandler

    handler = ProjectEnvironmentHandler(tmp_path, project_name="rollback")
    session = handler.get_sql_session()

    class _StubGlob:
        def commit_result(self):
            pass

        def commit_parameter(self):
            pass

        def close(self):
            pass

    run = type("Run", (), {"glob": _StubGlob()})()

    def _bad_insert(_run, sql_session):
        from silloncommon.database import SimulationTable

        row = SimulationTable(
            uuid="u1", name="n1", date="d", platform="p", hostname="h",
            meta_data={"bad": complex(1, 2)},
        )
        sql_session.add(row)
        return row

    monkeypatch.setattr(envhandler_module, "insert_simulation", _bad_insert)

    with pytest.raises(Exception):
        handler.commit_run(run)

    # The session must be usable again, or every later run is lost too.
    try:
        session.connection().execute(text("SELECT 1"))
    except PendingRollbackError:
        pytest.fail("session left in a failed transaction: no rollback happened")


# --- read path --------------------------------------------------------------


def test_missing_glob_data_raises_lookup_error(tmp_path):
    """The documented contract, and what callers catch."""
    from silloncore.engine import load_run_result

    snapshot = {
        "uuid": "does-not-exist",
        "name": "ghost",
        "results": {"coef": "coef"},
        "artifacts": {},
    }
    with pytest.raises(LookupError):
        load_run_result(tmp_path, snapshot, "coef")


def test_a_damaged_run_does_not_abort_a_whole_query(tmp_path):
    """Filtering must survive one run whose glob data is gone.

    load_run_result now raises LookupError instead of returning the pointer
    string. match_heavy calls it, so without a guard a single damaged run would
    take down a query over the entire project.
    """
    from silloncore.engine import match_heavy

    snapshot = {
        "uuid": "no-glob-on-disk",
        "name": "damaged",
        "results": {"loss": "loss"},
        "artifacts": {},
        "analyses": {},
    }
    # Must return False (this run does not match), not raise.
    assert match_heavy(tmp_path, snapshot, {"loss": lambda v: True}, None) is False
