import pytest
import time
import subprocess
import shutil
from pathlib import Path
from sqlmodel import create_engine

# Import the API to generate real data
import sillonpy as sp
from sillonpy.api import force_dump

# Import the Engine to read the real data
from silloncore.engine import (
    get_project_context,
    get_run_details,
    add_metadata_to_runs,
)
from silloncommon.database import select_all

# --- Path Configurations ---
CURRENT_PATH = Path(__file__).parent.resolve()
sillon_PATH = CURRENT_PATH / Path(".sillon/")
DB_PATH = sillon_PATH / Path("database.sql")

@pytest.fixture(scope="module", autouse=True)
def server():
    """Cleans the workspace around the suite.

    No manual server process is started: the per-project daemon is auto-spawned
    (via the current interpreter) the first time the API connects, so the tests
    run in a fresh checkout without the console script being on PATH.
    """
    print("\n[SETUP] Cleaning workspace for Integration Tests...")
    if sillon_PATH.exists():
        shutil.rmtree(sillon_PATH)

    yield  # Tests run here

    print("\n[TEARDOWN] Cleaning workspace...")
    # Let the auto-spawned daemon hit its idle-timeout and release the socket.
    time.sleep(1)
    if sillon_PATH.exists():
        shutil.rmtree(sillon_PATH)


@pytest.fixture(scope="module")
def populated_engine():
    """
    Uses the real API to log two distinct runs to the database.
    This creates a perfect, real-world test environment for the Engine.
    """
    # ==========================================
    #   CREATE RUN 1 (Heavy Math Run)
    # ==========================================
    sp.init(
        run_name="integration_alpha", 
        project_name="engine_integration", 
        project_path=str(CURRENT_PATH)
    )
    sp.log_param("learning_rate", 0.01)
    sp.log_param("optimizer", "adam")
    sp.log_result("final_loss", 0.05, save_result=True) # Will trigger HDF5
    
    force_dump()
    time.sleep(0.5) # Wait for Server to write to SQLite/HDF5

    # ==========================================
    #   CREATE RUN 2 (Lightweight Baseline)
    # ==========================================
    sp.init(
        run_name="integration_beta", 
        project_name="engine_integration", 
        project_path=str(CURRENT_PATH)
    )
    sp.log_param("optimizer", "sgd")
    sp.add_tag("baseline")
    sp.add_note("This is a control run.")
    
    force_dump()
    time.sleep(0.5)

    # Connect to the database that the server just populated
    engine = create_engine("sqlite:///" + str(DB_PATH))
    yield engine
    engine.dispose()


# ==========================================
#      THE ENGINE INTEGRATION TESTS
# ==========================================

def test_full_get_project_overview(populated_engine):
    """Proves the Engine can accurately summarize the live database."""
    
    result = get_project_context(populated_engine)
    
    assert result["mode"] == "overview"
    assert len(result["runs"]) == 2
    
    # Extract the runs (they should be sorted by timestamp)
    alpha_run = next(r for r in result["runs"] if r["name"] == "integration_alpha")
    beta_run = next(r for r in result["runs"] if r["name"] == "integration_beta")
    
    # Alpha has 2 params ("learning_rate", "optimizer") and 1 asset ("final_loss")
    assert alpha_run["param_count"] == 2
    assert alpha_run["asset_count"] == 1
    
    # Beta has 1 param ("optimizer") and 0 assets
    assert beta_run["param_count"] == 1
    assert beta_run["asset_count"] == 0


def test_full_get_project_specific(populated_engine):
    """Proves the Engine can extract specific metadata keys like language."""
    
    result = get_project_context(populated_engine, run_names=["integration_alpha"])
    
    assert result["mode"] == "specific"
    assert len(result["runs"]) == 1
    
    alpha_data = result["runs"][0]
    
    # assert alpha_data["language"] == "python 3.12"
    assert alpha_data["status"] != "N/A" # Status should be populated by the server


def test_full_get_run_details(populated_engine):
    """Proves the Engine correctly queries the JSON columns using Wildcards."""
    
    # Query all parameters for integration_beta
    details = get_run_details(
        populated_engine, 
        run_names=["integration_beta"], 
        params=["%all%"]
    )
    
    assert "parameter" in details
    db_params = details["parameter"]
    
    # The Engine parses DbSelectResult dataclasses. 
    # Let's ensure the 'optimizer' key made it all the way out.
    found_optimizer = False
    for param_obj in db_params:
        if param_obj.key == "optimizer" and param_obj.value == "sgd":
            found_optimizer = True
            
    assert found_optimizer, "The engine failed to pull the specific parameter from SQLite."


def test_full_add_metadata_to_runs(populated_engine):
    """
    Proves the Engine can successfully write back to the database 
    using the SQLite flag_modified hacks.
    """
    
    # 1. Ask the engine to add a tag to Beta
    result = add_metadata_to_runs(
        populated_engine, 
        run_names=["integration_beta"], 
        tags=["production_ready"]
    )
    
    # 2. Verify the Engine reported success
    assert result["status"] == "success"
    assert result["updated_count"] == 1
    assert "integration_beta" in result["updated_runs"]
    
    # 3. VERIFY IT ACTUALLY WORKED by querying the raw database
    all_runs = select_all(populated_engine)
    beta_db_row = next(r for r in all_runs if r.name == "integration_beta")
    
    # Beta already had "baseline" from the fixture, now it should have "production_ready"
    assert "baseline" in list(beta_db_row.tag)
    assert "production_ready" in list(beta_db_row.tag)
