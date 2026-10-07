"""Date filters have to mean the same thing for runs from different machines.

`--after`, `--before` and `prune --older-than` all used to parse the naive
`date` column with `strptime` and compare it to a naive bound. Within one
machine that is fine. Across two it is not: the bound is read in *your* local
time while the stored string is in whichever local time the run was logged in,
so a run can fall on the wrong side of a cutoff by the offset between them —
and `prune` deleting the wrong runs is not a recoverable mistake.
"""

import pytest
from sqlmodel import Session, SQLModel

from silloncommon.database import SimulationTable, make_engine, migrate_schema
from silloncore.engine import prune_runs, query_runs


def _row(name, date, started_at):
    return SimulationTable(
        uuid=f"uuid-{name}",
        name=name,
        date=date,
        started_at=started_at,
        parameters={"degree": 3},
        results={},
        meta_data={},
        tag=[],
        note=[],
        runtime="0:00:01",
        status="SUCCESS",
        platform="python",
        hostname="h",
        organisation="",
        author="a",
        project="p",
        hashes={},
        sillonversion="2.1.0",
    )


@pytest.fixture()
def engine(tmp_path):
    """Three runs on the same calendar day, in three timezones.

    Ordered by real instant: tokyo (00:00 UTC), paris (09:00 UTC),
    boston (18:00 UTC). Ordered by the naive string the old code compared:
    boston (13:00), paris (10:00)... which is to say, wrongly.
    """
    engine = migrate_schema(make_engine(tmp_path / "database.sql"))
    with Session(engine) as session:
        session.add(_row("tokyo", "2026-03-01-09:00:00", "2026-03-01T09:00:00+09:00"))
        session.add(_row("paris", "2026-03-01-10:00:00", "2026-03-01T10:00:00+01:00"))
        session.add(_row("boston", "2026-03-01-13:00:00", "2026-03-01T13:00:00-05:00"))
        session.commit()
    return engine


def _names(engine, **kwargs):
    return set(query_runs(engine, **kwargs))


# ==========================================
#              QUERY BOUNDS
# ==========================================
def test_a_bound_between_two_runs_splits_them_by_real_instant(engine):
    """14:00 UTC falls between paris (09:00 UTC) and boston (18:00 UTC)."""
    assert _names(engine, before="2026-03-01T14:00:00+00:00") == {"tokyo", "paris"}
    assert _names(engine, after="2026-03-01T14:00:00+00:00") == {"boston"}


def test_the_naive_string_order_would_disagree(engine):
    """Guard against the test being vacuous.

    Sorted as plain strings the order is tokyo, paris, boston — the same as
    the real order here only by luck of the hour chosen. What differs is
    *where a cutoff lands*, which the test above pins.
    """
    import sillonlab  # noqa: F401  (ensures the package imports cleanly)

    from silloncommon.database import select_run_index

    index = {e["name"]: e for e in select_run_index(engine)}
    assert index["tokyo"]["when"] < index["paris"]["when"] < index["boston"]["when"]
    # Boston's naive 13:00 reads as the latest of the three, but it is the
    # last in real time too — so compare the ones that actually invert.
    assert index["tokyo"]["date"] < index["paris"]["date"]


def test_a_bare_date_bound_is_local_midnight(engine):
    """What someone typing `--after 2026-03-01` means."""
    assert _names(engine, after="2026-02-28") == {"tokyo", "paris", "boston"}
    assert _names(engine, before="2026-03-02") == {"tokyo", "paris", "boston"}


def test_both_bounds_together(engine):
    found = _names(
        engine,
        after="2026-03-01T05:00:00+00:00",
        before="2026-03-01T14:00:00+00:00",
    )
    assert found == {"paris"}


def test_a_run_with_no_timestamp_is_excluded_by_a_bound(engine):
    with Session(engine) as session:
        session.add(_row("undated", None, None))
        session.commit()
    assert "undated" not in _names(engine, after="2026-01-01")


# ==========================================
#          PRUNE, WHICH IS PERMANENT
# ==========================================
def test_prune_older_than_uses_the_real_instant(engine, tmp_path):
    """The one that cannot be undone, so the one that must be right."""
    result = prune_runs(
        engine,
        tmp_path / ".sillon",
        before="2026-03-01T14:00:00+00:00",
        keep_metadata=False,
    )
    assert result["status"] == "success"
    assert set(result["pruned"]) == {"tokyo", "paris"}

    # Boston, which happened after the cutoff, is still there.
    assert _names(engine) == {"boston"}


def test_prune_refuses_without_a_scope(engine, tmp_path):
    """Unchanged behaviour, re-pinned because the bound parsing moved."""
    result = prune_runs(engine, tmp_path / ".sillon")
    assert result["status"] == "error"
    assert "Refusing to prune" in result["message"]
