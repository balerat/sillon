"""Lineage must follow the uuid, not the name cached in the edge.

A parent edge records `{"uuid", "name"}` — the name being the one the parent
had *on the machine where the link was made*. Once two machines' runs live in
one project, that name can belong to a different run locally: an import
suffixes the incoming `deg3` to `deg3~desktop`, so the edge's `"deg3"` now
names the local run instead of the parent it was written for.

Resolving by name there does not raise. It returns the wrong run's parameters,
which is a wrong number in a thesis rather than a traceback. These tests pin
the uuid as the thing a handle follows.
"""

import h5py
import numpy as np
import pytest
from sqlmodel import SQLModel, Session, create_engine

from silloncommon.database import sqlite_url, SimulationTable

import sillonlab as sl

# The local run, and an imported one that was also called "deg3" where it came
# from, suffixed on the way in. Deliberately differing only after many chars,
# so nothing passes by prefix luck.
LOCAL_UUID = "aaaaaaaa-0000-0000-0000-00000000000a"
FOREIGN_UUID = "bbbbbbbb-0000-0000-0000-00000000000b"
CHILD_UUID = "cccccccc-0000-0000-0000-00000000000c"
ABSENT_UUID = "dddddddd-0000-0000-0000-00000000000d"


def _row(uuid, name, degree, parents=None):
    return SimulationTable(
        uuid=uuid,
        name=name,
        date="2026-06-01-10:00:00",
        parameters={"degree": degree},
        results={},
        meta_data={},
        tag=[],
        note=[],
        parents=parents or [],
        runtime="0:00:01",
        status="SUCCESS",
        platform="python",
        hostname="testhost",
        organisation="",
        author="tester",
        project="merged",
        hashes={},
        sillonversion="2.0.2",
    )


@pytest.fixture()
def merged_project(tmp_path):
    """A project in the state an import leaves behind.

    `deg3` is local. `deg3~desktop` arrived from another machine where it was
    itself called `deg3`. The child's parent edge therefore carries
    `name="deg3"` pointing at the *foreign* uuid.
    """
    sillon_dir = tmp_path / ".sillon"
    (sillon_dir / "glob" / FOREIGN_UUID).mkdir(parents=True)
    with h5py.File(sillon_dir / "glob" / FOREIGN_UUID / "glob.hdf5", "w") as g:
        g.create_dataset("result/coef", data=np.array([9.0, 9.0]))

    engine = create_engine(sqlite_url(sillon_dir / "database.sql"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(_row(LOCAL_UUID, "deg3", 3))
        session.add(_row(FOREIGN_UUID, "deg3~desktop", 99))
        session.add(
            _row(
                CHILD_UUID,
                "refined",
                4,
                parents=[{"uuid": FOREIGN_UUID, "name": "deg3", "relation": "inherit"}],
            )
        )
        session.commit()
    engine.dispose()
    return tmp_path


# ==========================================
#              THE WRONG-RUN BUG
# ==========================================
def test_parent_follows_the_uuid_not_the_stale_name(merged_project):
    """The edge says "deg3"; locally that name is someone else's."""
    project = sl.load_project(merged_project)
    parent = project.get("refined").parents()[0]

    # Assert on the value, not the name: the name is exactly what was wrong.
    assert parent.parameters["degree"] == 99
    assert parent.uuid == FOREIGN_UUID
    assert parent.name == "deg3~desktop"


def test_the_local_namesake_is_untouched(merged_project):
    """Sanity: the run the buggy lookup used to return is still itself."""
    project = sl.load_project(merged_project)
    assert project.get("deg3").parameters["degree"] == 3
    assert project.get("deg3").uuid == LOCAL_UUID


def test_children_follow_the_uuid(merged_project):
    project = sl.load_project(merged_project)
    children = project.get("deg3~desktop").children()
    assert [c.uuid for c in children] == [CHILD_UUID]
    assert children[0].parameters["degree"] == 4


def test_the_local_namesake_has_no_children(merged_project):
    """Reverse lineage keys on uuid, so the namesake must not inherit them."""
    project = sl.load_project(merged_project)
    assert len(project.get("deg3").children()) == 0


# ==========================================
#              DANGLING EDGES
# ==========================================
def test_a_parent_that_was_never_imported(tmp_path):
    """Importing a child without its parent leaves a true but unwalkable edge."""
    sillon_dir = tmp_path / ".sillon"
    sillon_dir.mkdir(parents=True)
    engine = create_engine(sqlite_url(sillon_dir / "database.sql"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            _row(
                CHILD_UUID,
                "orphan",
                4,
                parents=[{"uuid": ABSENT_UUID, "name": "baseline"}],
            )
        )
        session.commit()
    engine.dispose()

    run = sl.load_project(tmp_path).get("orphan")

    # The edge is still a true statement about where this run came from.
    assert run.parent_links() == [{"uuid": ABSENT_UUID, "name": "baseline"}]

    # Walking it fails, and says why rather than looking like a typo.
    with pytest.raises(LookupError) as excinfo:
        run.parents()[0].parameters
    message = str(excinfo.value)
    assert "baseline" in message
    assert ABSENT_UUID in message
    assert "never imported" in message


# ==========================================
#            HANDLE CONSTRUCTION
# ==========================================
def test_a_handle_can_be_built_from_a_uuid_alone(merged_project):
    from sillonlab.run import Run

    project = sl.load_project(merged_project)
    run = Run(uuid=FOREIGN_UUID, engine=project.engine, storage_root=project.storage_root)
    assert run.parameters["degree"] == 99
    assert run.name == "deg3~desktop"


def test_a_handle_needs_one_of_the_two(merged_project):
    from sillonlab.run import Run

    project = sl.load_project(merged_project)
    with pytest.raises(ValueError, match="name or a uuid"):
        Run(engine=project.engine, storage_root=project.storage_root)


def test_handles_from_the_run_table_carry_their_uuid(merged_project):
    """`Project.runs()` has the uuid in hand already; it should pass it on."""
    project = sl.load_project(merged_project)
    assert all(run.uuid is not None for run in project.runs())
