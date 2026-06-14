import pytest
import time
import shutil
from pathlib import Path

from sqlmodel import create_engine
import h5py

# High-level API imports
import sillonpy as sp
from sillonpy.api import force_dump, set_context

# Database query imports
from silloncommon.database import (
    select_param_all,
    select_result_all,
    select_metadata_all,
    select_all
)

# --- Path Configurations ---
CURRENT_PATH = Path(__file__).parent.resolve()
SILLON_PATH = CURRENT_PATH / Path(".sillon/")
DB_PATH = SILLON_PATH / Path("database.sql")
ARTIFACT_PATH = SILLON_PATH / Path("artifact/")


@pytest.fixture(scope="module", autouse=True)
def clean_workspace():
    """Cleans the .simply workspace before and after the suite.

    No manual server process: the per-project daemon is auto-spawned on the
    first API call that needs it."""
    print("\n[SETUP] Cleaning workspace...")
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH)

    yield

    print("\n[TEARDOWN] Cleaning up...")
    set_context(None)
    # Let the auto-spawned daemon hit idle-timeout / release the socket
    # before we remove the project dir.
    time.sleep(1)
    if SILLON_PATH.exists():
        shutil.rmtree(SILLON_PATH)


@pytest.fixture
def api_env():
    """Initializes the API and DB connection for EVERY test."""
    # Starting the tracker auto-spawns the project daemon if it isn't running.
    sp.init(project_name="api_integration_tests", project_path=str(CURRENT_PATH))

    engine = create_engine("sqlite:///" + str(DB_PATH))

    yield engine

    engine.dispose()
    set_context(None)


# ==========================================
#               THE API TESTS
# ==========================================
def test_api_track_decorator(clean_workspace):
    """Verifies the @track decorator intercepts args, kwargs, and saves results to HDF5."""
    engine = create_engine("sqlite:///" + str(DB_PATH))

    @sp.track(run_name="decorator_test", author="doph", save_result=True, project_path=str(CURRENT_PATH))
    def calculate_drag(velocity, area, drag_coeff=0.5):
        time.sleep(0.1)
        return velocity * area * drag_coeff

    result = calculate_drag(100, 2.5, drag_coeff=0.4)
    assert result == 100.0

    force_dump()
    time.sleep(0.5)

    all_runs = select_all(engine)
    latest_run = all_runs[-1]

    # --- VERIFY SQLITE (The Lightweight Data) ---
    assert latest_run.name == "decorator_test"

    params = latest_run.parameters
    assert params["sillon.python.tracked_function_args.calculate_drag"] == [100, 2.5]
    assert params["sillon.python.tracked_function_kwargs.calculate_drag"] == {"drag_coeff": 0.4}

    results = latest_run.results
    pointer_string = "sillon.python.tracked_function_result.calculate_drag"
    assert pointer_string in results
    assert results[pointer_string] == pointer_string

    # --- VERIFY HDF5 GLOB (The Heavy Data) ---
    found_glob = next((SILLON_PATH / "glob").rglob("glob.hdf5"), None)
    assert found_glob is not None
    print(f"\n[TEST] Opening HDF5 at: {found_glob.resolve()}", flush=True)

    with h5py.File(found_glob, "r") as glob_file:
        assert "result" in glob_file
        res_group = glob_file["result"]
        assert pointer_string in res_group
        saved_value = res_group[pointer_string][()]
        assert saved_value == 100.0

    engine.dispose()


def test_api_log_param(api_env):
    engine = api_env

    sp.log_param("test_velocity", 150.5)
    sp.log_param("test_solver", "OpenFOAM")

    force_dump()
    time.sleep(0.5)

    db_params = select_param_all(engine)
    assert db_params != []

    latest_params = db_params[-1]
    assert latest_params["test_velocity"] == 150.5
    assert latest_params["test_solver"] == "OpenFOAM"


def test_api_log_result(api_env):
    engine = api_env

    dummy_file = CURRENT_PATH / "dummy_result.txt"
    dummy_file.write_text("Hello sillonTrack!")

    sp.log_result("mesh_output", path=str(dummy_file))

    force_dump()
    time.sleep(0.5)

    found_artifact = next(ARTIFACT_PATH.rglob("dummy_result.txt"), None)
    assert found_artifact is not None
    assert found_artifact.exists()

    dummy_file.unlink()


def test_api_add_metadata(api_env):
    engine = api_env

    sp.add_metadata("user", "doph")
    sp.add_metadata("machine", "dalaran-8")

    force_dump()
    time.sleep(0.5)

    db_metadata = select_metadata_all(engine)
    assert db_metadata != []
    latest_meta = db_metadata[-1]
    assert latest_meta["sillon.user_metadata.user"] == "doph"


def test_api_add_note_and_tag(api_env):
    engine = api_env

    sp.add_note("This run crashed because of mesh divergence.")
    sp.add_tag("diverged")
    sp.add_tag("test_run")

    force_dump()
    time.sleep(0.5)

    all_runs = select_all(engine)
    assert all_runs != []

    latest_run = all_runs[-1]

    assert "This run crashed because of mesh divergence." in list(latest_run.note)
    assert "diverged" in list(latest_run.tag)
    assert "test_run" in list(latest_run.tag)


def test_api_log_param_variations(api_env):
    engine = api_env

    # Method 1: Standard Key-Value pair
    sp.log_param("learning_rate", 0.001)

    # Method 2: Passing a Dictionary
    hyperparams = {
        "batch_size": 32,
        "optimizer": "Adam"
    }
    sp.log_param(hyperparams)

    # Method 3: Passing **kwargs directly
    sp.log_param(dropout=0.5, epochs=100)

    force_dump()
    time.sleep(0.5)

    db_params = select_param_all(engine)
    assert db_params != []

    latest_params = db_params[-1]
    assert latest_params["learning_rate"] == 0.001
    assert latest_params["batch_size"] == 32
    assert latest_params["optimizer"] == "Adam"
    assert latest_params["dropout"] == 0.5
    assert latest_params["epochs"] == 100


def test_api_add_metadata_variations(api_env):
    engine = api_env

    sp.add_metadata("user", "doph")

    env_data = {
        "os": "linux",
        "python_version": "3.11"
    }
    sp.add_metadata(env_data)

    force_dump()
    time.sleep(0.5)

    db_metadata = select_metadata_all(engine)
    assert db_metadata != []

    latest_meta = db_metadata[-1]
    assert latest_meta["sillon.user_metadata.user"] == "doph"
    assert latest_meta["sillon.user_metadata.os"] == "linux"
    assert latest_meta["sillon.user_metadata.python_version"] == "3.11"


def test_api_init_custom_fields(clean_workspace):
    """Verifies that custom init arguments make it all the way to the database."""
    engine = create_engine("sqlite:///" + str(DB_PATH))

    sp.init(
        run_name="Apollo_11",
        organisation="NASA",
        author="Neil",
        project_name="Moon_Landing",
        project_path=str(CURRENT_PATH)
    )

    sp.log_param("status", "go_for_launch")

    force_dump()
    time.sleep(0.5)

    all_runs = select_all(engine)
    assert all_runs != []

    latest_run = all_runs[-1]
    assert latest_run.name == "Apollo_11"
    assert latest_run.organisation == "NASA"
    assert latest_run.author == "Neil"
    assert latest_run.project == "Moon_Landing"

    engine.dispose()


def test_api_error_handling(api_env):
    """Fires bad inputs at the API to ensure value errors are raised."""

    with pytest.raises(ValueError, match="Invalid Entry"):
        sp.log_param()

    with pytest.raises(ValueError, match="but no value"):
        sp.log_param("lonely_key")

    with pytest.raises(ValueError, match="Ambiguous input"):
        sp.log_result(id="mesh", value=100, path="/fake/path.txt")

    with pytest.raises(ValueError, match="Missing data"):
        sp.log_result()

    with pytest.raises(ValueError, match="but no value"):
        sp.add_metadata("lonely_meta")

    with pytest.raises(ValueError, match="Note must be of type str"):
        sp.add_note(404)
