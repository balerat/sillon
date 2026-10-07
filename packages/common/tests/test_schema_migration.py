"""Opening an old database must bring it forward, and say what it is.

Three gaps this pins down:

- `migrate_schema` only ever ALTERed `simulationtable`, so a column added to
  artifacts, figures or analyses was never backfilled into an existing project
  — `create_all()` skips a table that is already there.
- Nothing recorded a schema version anywhere, so two machines on different
  sillon versions could not tell, and the older one silently dropped fields.
- `uuid` had no uniqueness, so importing the same run twice produced a shadow
  row: readers take `.first()` and never see it, while the index counts it.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from silloncommon import timestamps
from silloncommon.database import (
    SCHEMA_VERSION,
    UUID_UNIQUE_INDEX,
    ArtifactTable,
    SimulationTable,
    make_engine,
    migrate_schema,
    schema_version,
    select_run_index,
)


def _row(uuid, name, date="2026-06-01-10:00:00", started_at=None):
    return SimulationTable(
        uuid=uuid,
        name=name,
        date=date,
        started_at=started_at,
        parameters={},
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
        sillonversion="2.0.2",
    )


@pytest.fixture()
def engine(tmp_path):
    return migrate_schema(make_engine(tmp_path / "database.sql"))


def _columns(engine, table):
    with engine.connect() as conn:
        return {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})")}


def _indexes(engine, table):
    with engine.connect() as conn:
        return {r[1] for r in conn.exec_driver_sql(f"PRAGMA index_list('{table}')")}


# ==========================================
#              THE VERSION MARKER
# ==========================================
def test_a_fresh_database_records_the_current_version(engine):
    assert schema_version(engine) == SCHEMA_VERSION


def test_a_legacy_database_reads_as_zero_then_migrates(tmp_path):
    """Everything written before the pragma existed."""
    raw = make_engine(tmp_path / "legacy.sql")
    SQLModel.metadata.create_all(raw)
    assert schema_version(raw) == 0

    migrate_schema(raw)
    assert schema_version(raw) == SCHEMA_VERSION


def test_a_newer_database_is_not_downgraded(engine):
    """So the sillon that wrote it can still tell this one opened it."""
    with engine.begin() as conn:
        conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION + 7}")
    migrate_schema(engine)
    assert schema_version(engine) == SCHEMA_VERSION + 7


def test_migrating_twice_changes_nothing(engine):
    before = (_columns(engine, "simulationtable"), _indexes(engine, "simulationtable"))
    migrate_schema(engine)
    migrate_schema(engine)
    assert (_columns(engine, "simulationtable"), _indexes(engine, "simulationtable")) == before


# ==========================================
#          ALL FOUR TABLES, NOT ONE
# ==========================================
def test_a_missing_column_is_added_to_a_child_table(tmp_path):
    """The gap: only `simulationtable` was ever ALTERed."""
    path = tmp_path / "old.sql"
    engine = make_engine(path)
    SQLModel.metadata.create_all(engine)

    # Simulate an older file by dropping a column from a child table. SQLite
    # cannot DROP COLUMN on older versions, so rebuild the table without it.
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE artifacttable")
        conn.exec_driver_sql(
            "CREATE TABLE artifacttable ("
            " id INTEGER NOT NULL PRIMARY KEY,"
            " name VARCHAR,"
            " hsh VARCHAR NOT NULL,"
            " run_id INTEGER)"
        )
    assert "path" not in _columns(engine, "artifacttable")

    migrate_schema(engine)
    assert "path" in _columns(engine, "artifacttable")


def test_every_declared_column_exists_after_migration(engine):
    for table in SQLModel.metadata.tables.values():
        declared = {c.name for c in table.columns}
        assert declared <= _columns(engine, table.name), table.name


# ==========================================
#              UUID UNIQUENESS
# ==========================================
def test_the_unique_index_is_created(engine):
    assert UUID_UNIQUE_INDEX in _indexes(engine, "simulationtable")


def test_the_same_run_cannot_be_inserted_twice(engine):
    with Session(engine) as session:
        session.add(_row("dup-uuid", "deg3"))
        session.commit()

    with pytest.raises(IntegrityError):
        with Session(engine) as session:
            session.add(_row("dup-uuid", "deg3~imported"))
            session.commit()


def test_a_database_that_already_has_duplicates_still_opens(tmp_path):
    """Refusing to open it would strand whatever is already in there.

    The index is simply not created; `sillon check` reports the duplicates.
    """
    path = tmp_path / "dirty.sql"
    engine = make_engine(path)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(_row("same", "one"))
        session.add(_row("same", "two"))
        session.commit()

    migrate_schema(engine)  # must not raise

    assert UUID_UNIQUE_INDEX not in _indexes(engine, "simulationtable")
    # The other indexes were not taken down with it.
    assert "ix_simulationtable_name" in _indexes(engine, "simulationtable")
    with Session(engine) as session:
        assert len(session.exec(select(SimulationTable)).all()) == 2


# ==========================================
#          started_at AND BACKFILL
# ==========================================
def test_older_runs_are_backfilled_from_their_date(tmp_path):
    engine = make_engine(tmp_path / "pre.sql")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(_row("u1", "winter", date="2026-01-15-09:00:00"))
        session.add(_row("u2", "summer", date="2026-07-15-09:00:00"))
        session.commit()

    migrate_schema(engine)

    with Session(engine) as session:
        rows = {r.name: r for r in session.exec(select(SimulationTable)).all()}
    for row in rows.values():
        assert row.started_at, f"{row.name} was not backfilled"
        # The offset in force on that date, so the instant is preserved.
        assert timestamps.to_aware(row.date, row.started_at).strftime(
            "%Y-%m-%d %H:%M"
        ) == timestamps.to_aware(row.date).strftime("%Y-%m-%d %H:%M")


def test_an_unparseable_date_is_left_alone(tmp_path):
    """A junk timestamp must not stop the migration."""
    engine = make_engine(tmp_path / "junk.sql")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(_row("u1", "bad", date="not a date"))
        session.commit()

    migrate_schema(engine)

    with Session(engine) as session:
        assert session.exec(select(SimulationTable)).first().started_at is None


def test_a_real_started_at_is_not_overwritten(tmp_path):
    """An imported run arrives with the originating machine's timestamp."""
    engine = make_engine(tmp_path / "imported.sql")
    SQLModel.metadata.create_all(engine)
    foreign = "2026-03-01T09:00:00-05:00"
    with Session(engine) as session:
        session.add(_row("u1", "from_boston", date="2026-03-01-09:00:00", started_at=foreign))
        session.commit()

    migrate_schema(engine)

    with Session(engine) as session:
        assert session.exec(select(SimulationTable)).first().started_at == foreign


# ==========================================
#        ORDERING ACROSS TIMEZONES
# ==========================================
def test_the_index_orders_by_the_real_instant(engine):
    """A 14:00 in Paris happened *before* a 13:00 in Boston that day.

    Sorting the naive `date` strings puts them the other way round, which is
    exactly what a merged project would show.
    """
    with Session(engine) as session:
        session.add(
            _row("paris", "paris", date="2026-03-01-14:00:00",
                 started_at="2026-03-01T14:00:00+01:00")   # 13:00 UTC
        )
        session.add(
            _row("boston", "boston", date="2026-03-01-13:00:00",
                 started_at="2026-03-01T13:00:00-05:00")   # 18:00 UTC
        )
        session.commit()

    by_name = {e["name"]: e for e in select_run_index(engine)}
    assert by_name["paris"]["when"] < by_name["boston"]["when"]
    # And the naive strings really do disagree, so the test is not vacuous.
    assert by_name["paris"]["date"] > by_name["boston"]["date"]
