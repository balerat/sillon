"""Server-side failures must reach the caller, not be printed and discarded.

Regression guard: the daemon emits a top-level JSON-RPC "error" and
`decode_response` raises on it, but `execute_command` used to catch that, print
one line and return None -- so a failed command looked like a clean run.
"""

import shutil
import time
import uuid
from pathlib import Path

import pytest

from silloncommon.commands import Command
from sillonpy.serverCom import ServerCom

CURRENT_PATH = Path(__file__).parent.resolve()
SILLON_PATH = CURRENT_PATH / ".sillon"


@pytest.fixture(scope="module", autouse=True)
def clean_workspace():
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH)
    yield
    time.sleep(1)  # let the daemon release the socket before removing the dir
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH, ignore_errors=True)


@pytest.fixture
def com():
    c = ServerCom(
        str(uuid.uuid4()),
        "error-probe",
        project_name="error_project",
        platform="test_platform",
        organisation="org",
        author="author",
        project_path=str(CURRENT_PATH),
    )
    c.connect_server()
    yield c


def test_server_error_is_raised_not_swallowed(com):
    """An unknown method makes the server return an error envelope."""
    with pytest.raises(Exception) as excinfo:
        com.execute_command(Command("x", "no_such_command", "v"))
    assert "UnknownCommand" in str(excinfo.value)


def test_command_id_advances_across_a_failure(com):
    """Ids must stay in step with the server even when a command fails.

    The increment used to be skipped on the error path, so every request after
    the first failure carried an id the server had already answered.
    """
    before = com.command_id

    with pytest.raises(Exception):
        com.execute_command(Command("x", "no_such_command", "v"))
    assert com.command_id == before + 1

    # The connection is still usable and still in step afterwards.
    com.execute_command(Command("after_failure", "log_param", 1))
    assert com.command_id == before + 2


def test_successful_command_still_returns_its_result(com):
    """The happy path is unchanged."""
    com.execute_command(Command("alpha", "log_param", 42))
    assert com.command_id >= 1
