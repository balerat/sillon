"""A stored run must say which sillon wrote it, not which one filed it.

`insert_simulation` hard-coded `sillonversion=sillon_VERSION` — the version of
whatever process happened to be doing the insert. For a run being logged that
is the same thing. For a run arriving from another machine it is not: stamping
the local version destroys the only record of what actually produced it, which
matters precisely when you are trying to work out why two runs disagree.

`insert_simulation` is duck-typed on a live `Simulation`, so these tests use
the same shape rather than constructing one — which is also a check that the
attributes an importer will have to supply are the ones it reads.
"""

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from silloncommon import __version__ as LOCAL_VERSION
from silloncommon.database import (
    SimulationTable,
    insert_simulation,
    make_engine,
    migrate_schema,
)


@dataclass
class _Hashes:
    source: str = ""
    git: str = ""


def _run(**over):
    """The attribute surface `insert_simulation` reads off a Simulation."""
    base = dict(
        run_id="uuid-1",
        run_name="deg3",
        date="2026-03-01-10:00:00",
        started_at="2026-03-01T10:00:00+01:00",
        parameters={"degree": 3},
        results={},
        figures={},
        metadata={},
        tags=[],
        notes=[],
        parents=[],
        platform="python",
        hostname="elsewhere",
        organisation="",
        author="someone",
        hashes=_Hashes(),
        project_name="merged",
        status="SUCCESS",
        logic_version="abc123",
        runtime="0:00:01",
    )
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture()
def session(tmp_path):
    engine = migrate_schema(make_engine(tmp_path / "database.sql"))
    with Session(engine) as session:
        yield session


def _stored(session):
    return session.exec(select(SimulationTable)).one()


def test_a_logged_run_gets_the_local_version(session):
    """Unchanged behaviour: nothing supplies a version, so ours applies."""
    insert_simulation(_run(), session)
    session.commit()
    assert _stored(session).sillonversion == LOCAL_VERSION


def test_a_supplied_version_is_preserved(session):
    """What an import needs: the originating machine's version survives."""
    insert_simulation(_run(sillonversion="1.5.0"), session)
    session.commit()
    assert _stored(session).sillonversion == "1.5.0"


def test_an_empty_version_falls_back_rather_than_storing_nothing(session):
    """A blank is missing information, not a claim that it was written by ''."""
    insert_simulation(_run(sillonversion=""), session)
    session.commit()
    assert _stored(session).sillonversion == LOCAL_VERSION


def test_the_offset_aware_timestamp_is_carried_through(session):
    insert_simulation(_run(), session)
    session.commit()
    row = _stored(session)
    assert row.date == "2026-03-01-10:00:00"
    assert row.started_at == "2026-03-01T10:00:00+01:00"


def test_a_run_without_started_at_still_inserts(session):
    """Anything built the old way, including every existing caller."""
    run = _run()
    del run.started_at
    insert_simulation(run, session)
    session.commit()
    assert _stored(session).started_at is None
