import pytest
import time
import subprocess
import shutil
from pathlib import Path

from sqlmodel import create_engine
import h5py

# High-level API imports
import simplypy as sp
from simplypy.api import force_dump

# Database query imports
from simplycommon.database import (
    select_param_all, 
    select_result_all, 
    select_metadata_all, 
    select_all
)

# --- Path Configurations ---
CURRENT_PATH = Path(__file__).parent.resolve()
SIMPLY_PATH = CURRENT_PATH / Path(".simply/")
DB_PATH = SIMPLY_PATH / Path("database.sql")
ARTIFACT_PATH = SIMPLY_PATH / Path("artifact/")


@pytest.fixture(scope="module", autouse=True)
def server():
    """Starts the background server ONCE for the entire test suite."""
    print("\n[SETUP] Starting background SimplyCore server...")
    
    # Clean up any old database files before the test suite starts
    # if SIMPLY_PATH.exists():
    #     shutil.rmtree(SIMPLY_PATH)
        
    server_process = subprocess.Popen(["simply-server-daemon"])
    time.sleep(2)  # Give the server time to bind to the TCP port

    yield  # Tests run here

    print("\n[TEARDOWN] Shutting down server...")
    server_process.terminate()
    server_process.wait()
    # if SIMPLY_PATH.exists():
    #     shutil.rmtree(SIMPLY_PATH)


@pytest.fixture
def api_env():
    """Initializes the API and DB connection for EVERY test."""
    # 1. Start the tracker (creates a new run_id internally)
    sp.init(project_name="api_integration_tests", project_path=str(CURRENT_PATH))
    
    # 2. Connect to the database
    engine = create_engine("sqlite:///" + str(DB_PATH))

    yield engine
    # 3. Teardown: Disconnect from the database
    engine.dispose()
    # force_dump()  # <--- Guarantee the context is cleared so atexit doesn't crash!
    

# ==========================================
#               THE API TESTS
# ==========================================
def test_api_track_decorator(server):
    """Verifies the @track decorator intercepts args, kwargs, and saves results to HDF5."""
    engine = create_engine("sqlite:///" + str(DB_PATH))

    # 1. Define a tracked function
    @sp.track(run_name="decorator_test", author="doph", save_result=True, project_path=str(CURRENT_PATH))
    def calculate_drag(velocity, area, drag_coeff=0.5):
        time.sleep(0.1) 
        return velocity * area * drag_coeff

    # 2. Execute it
    result = calculate_drag(100, 2.5, drag_coeff=0.4)
    assert result == 100.0 

    # 3. Dump to DB & HDF5
    force_dump()
    time.sleep(0.5)

    all_runs = select_all(engine)
    latest_run = all_runs[-1]

    # --- VERIFY SQLITE (The Lightweight Data) ---
    assert latest_run.name == "decorator_test"
    
    params = latest_run.parameters
    assert params["simply.python.tracked_function_args.calculate_drag"] == [100, 2.5]
    assert params["simply.python.tracked_function_kwargs.calculate_drag"] == {"drag_coeff": 0.4}

    # Verify the database just holds the POINTER, not the value!
    results = latest_run.results
    pointer_string = "simply.python.tracked_function_result.calculate_drag"
    assert pointer_string in results
    assert results[pointer_string] == pointer_string # Or whatever pointer format you use

    # --- VERIFY HDF5 GLOB (The Heavy Data) ---
    found_glob = next((SIMPLY_PATH / "glob").rglob("glob.hdf5"), None)
    assert found_glob is not None
    print(f"\n[TEST] Opening HDF5 at: {found_glob.resolve()}", flush=True)

    with h5py.File(found_glob, "r") as glob_file:
        # Check if the 'result' group exists
        assert "result" in glob_file
        res_group = glob_file["result"]
        
        # Check if our specific result made it in
        assert pointer_string in res_group
        
        # Extract the value from the HDF5 dataset. 
        # using [()] extracts the scalar value from the h5py dataset object
        saved_value = res_group[pointer_string][()]
        assert saved_value == 100.0

    engine.dispose()

def test_api_log_param(api_env):
    engine = api_env
    
    # 1. Use the API
    sp.log_param("test_velocity", 150.5)
    sp.log_param("test_solver", "OpenFOAM")
    
    # 2. Force the server to dump to SQLite
    force_dump()
    time.sleep(0.5) # Buffer for database write
    
    # 3. Assert the data made it to the database
    db_params = select_param_all(engine)
    assert db_params != []
    
    # Assuming select_param returns a list of dictionaries like [{"test_velocity": 150.5, ...}]
    latest_params = db_params[-1] 
    assert latest_params["test_velocity"] == 150.5
    assert latest_params["test_solver"] == "OpenFOAM"


def test_api_log_result(api_env):
    engine = api_env
    
    # Create a dummy file to act as our artifact
    dummy_file = CURRENT_PATH / "dummy_result.txt"
    dummy_file.write_text("Hello SimplyTrack!")
    
    # 1. Use the API
    sp.log_result("mesh_output", path=str(dummy_file))
    
    # 2. Force dump
    force_dump()
    time.sleep(0.5)
    
    # 3. Assert the file was copied into the artifact folder
    found_artifact = next(ARTIFACT_PATH.rglob("dummy_result.txt"), None)
    assert found_artifact is not None
    assert found_artifact.exists()
    
    # 4. Cleanup the dummy file
    dummy_file.unlink()


def test_api_add_metadata(api_env):
    engine = api_env
    
    # 1. Use the API
    sp.add_metadata("user", "doph")
    sp.add_metadata("machine", "dalaran-8")
    
    # 2. Force dump
    force_dump()
    time.sleep(0.5)
    
    # 3. Assert
    db_metadata = select_metadata_all(engine)
    assert db_metadata != []
    latest_meta = db_metadata[-1]
    assert latest_meta["simply.user_metadata.user"] == "doph"


def test_api_add_note_and_tag(api_env):
    engine = api_env
    
    # 1. Use the API
    sp.add_note("This run crashed because of mesh divergence.")
    sp.add_tag("diverged")
    sp.add_tag("test_run")
    
    # 2. Force dump
    force_dump()
    time.sleep(0.5)
    
    # 3. Assert (Checking the raw SimulationTable since we didn't write specific select_note functions)
    all_runs = select_all(engine)
    assert all_runs != []
    
    latest_run = all_runs[-1]
    
    # Verify the note exists in the JSON column
    assert "This run crashed because of mesh divergence." in list(latest_run.note)
    print("AAAAA", list(latest_run.tag)) 
    # Verify the tags exist in the JSON column
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
    
    # Force the server to dump
    force_dump()
    time.sleep(0.5)
    
    # Assert ALL of them made it into the exact same run dictionary
    db_params = select_param_all(engine)
    assert db_params != []
    
    latest_params = db_params[-1] 
    
    # If your API handled the unpacking correctly, all 5 of these will pass!
    assert latest_params["learning_rate"] == 0.001
    assert latest_params["batch_size"] == 32
    assert latest_params["optimizer"] == "Adam"
    assert latest_params["dropout"] == 0.5
    assert latest_params["epochs"] == 100


def test_api_add_metadata_variations(api_env):
    engine = api_env
    
    # Method 1: Standard
    sp.add_metadata("user", "doph")
    
    # Method 2: Dictionary
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
    
    # Verify everything unpacked beautifully
    assert latest_meta["simply.user_metadata.user"] == "doph"
    assert latest_meta["simply.user_metadata.os"] == "linux"
    assert latest_meta["simply.user_metadata.python_version"] == "3.11"

def test_api_init_custom_fields(server):
    """Verifies that custom init arguments make it all the way to the database."""
    engine = create_engine("sqlite:///" + str(DB_PATH))
    
    # 1. Manually initialize with full custom fields
    sp.init(
        run_name="Apollo_11",
        organisation="NASA",
        author="Neil",
        project_name="Moon_Landing",
        project_path=str(CURRENT_PATH)
    )
    
    # Need to log at least one thing to ensure the tracker actually processes
    sp.log_param("status", "go_for_launch")
    
    # 2. Force dump and clean the context
    force_dump()
    time.sleep(0.5)
    
    # 3. Verify the database caught the top-level metadata
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
    
    # 1. Test log_param empty fail
    with pytest.raises(ValueError, match="Invalid Entry"):
        sp.log_param()
        
    # 2. Test log_param string without value
    with pytest.raises(ValueError, match="but no value"):
        sp.log_param("lonely_key")
        
    # 3. Test log_result ambiguous input
    with pytest.raises(ValueError, match="Ambiguous input"):
        sp.log_result(id="mesh", value=100, path="/fake/path.txt")
        
    # 4. Test log_result completely empty
    with pytest.raises(ValueError, match="Missing data"):
        sp.log_result()
        
    # 5. Test add_metadata string without value
    with pytest.raises(ValueError, match="but no value"):
        sp.add_metadata("lonely_meta")
        
    # 6. Test add_note with bad type (int instead of str)
    with pytest.raises(ValueError, match="Note must be of type str"):
        sp.add_note(404)
        
    # Since these all failed gracefully, we don't even need to force_dump
# def test_api_log_result_variations(api_env):
#     engine = api_env
#
#     # We will test logging standard values (like metrics) rather than just files here
#
#     # Method 1: Standard
#     sp.log_result("final_loss", 0.04)
#
#     # Method 2: Dictionary
#     metrics = {
#         "accuracy": 0.98,
#         "f1_score": 0.95
#     }
#     sp.log_result(metrics)
#
#     # Method 3: Kwargs
#     sp.log_result(val_loss=0.06, val_accuracy=0.96)
#
#     force_dump()
#     time.sleep(0.5)
#
#     db_results = select_result(engine)
#     assert db_results != []
#
#     latest_results = db_results[-1]
#
#     # Check that all the numeric metrics were saved properly
#     print("Final losssss:", latest_results["final_loss"])
#     assert latest_results["final_loss"] == 0.04
#     assert latest_results["accuracy"] == 0.98
#     assert latest_results["f1_score"] == 0.95
#     assert latest_results["val_loss"] == 0.06
#     assert latest_results["val_accuracy"] == 0.96
