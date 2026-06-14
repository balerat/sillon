from pathlib import Path
from sqlmodel import create_engine
import shutil
import pytest
import time
import uuid

from sillonpy.serverCom import ServerCom
from sillonpy.api import set_context
from silloncommon.commands import LogParamCmd, LogResultCmd, DumpCmd
from silloncommon.database import select_param_all, select_all

CURRENT_PATH = Path(__file__).parent.resolve()
SILLON_PATH = CURRENT_PATH / Path(".sillon/")
DB_PATH = SILLON_PATH / Path("database.sql")
ARTIFACT_PATH = SILLON_PATH / Path("artifact/")


@pytest.fixture(scope="module", autouse=True)
def clean_workspace():
    """Ensure a clean .sillon dir before the suite, and tear it down after.

    No manual server process: the daemon is auto-spawned per-project on the
    first ServerCom connection."""
    print("\n[SETUP] Cleaning workspace...")
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH)

    yield

    print("\n[TEARDOWN] Cleaning up...")
    set_context(None)
    # Give the auto-spawned daemon a moment to hit its idle-timeout / release
    # the socket before we delete the project dir.
    time.sleep(1)
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH)


@pytest.fixture
def env():
    com = ServerCom(
        str(uuid.uuid4()),
        "basic-project",
        project_path=str(CURRENT_PATH),
        platform="test_platform",
        project_name="project_name",
        author="author",
        organisation="org_test",
    )
    # First ServerCom for this project_path auto-spawns the daemon; wait for
    # readiness rather than assuming it's already bound.
    engine = create_engine("sqlite:///" + str(DB_PATH))

    yield com, engine

    engine.dispose()
    com = None


def test_parameter(env):
    com, engine = env
    com.execute_command(LogParamCmd("test_parameter", 0))
    com.execute_command(DumpCmd())
    time.sleep(1)
    assert select_all(engine) is not None
    assert select_param_all(engine) == [{"test_parameter": 0}]


def test_result(env):
    com, _ = env
    command = LogResultCmd(
        "test",
        {
            "value": None,
            "path": str(CURRENT_PATH / Path("test.txt")),
            "save_result": True,
        },
    )
    com.execute_command(command)
    com.execute_command(DumpCmd())
    time.sleep(1)
    assert next(ARTIFACT_PATH.rglob("test.txt"), None)
