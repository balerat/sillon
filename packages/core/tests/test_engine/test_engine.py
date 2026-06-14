import pytest
from unittest.mock import patch

# Import the functions from your engine
from silloncore.engine import (
    get_project_context,
    get_run_details,
    add_metadata_to_runs,
)

# ==========================================
#      TESTING GET_PROJECT_CONTEXT
# ==========================================

@patch("silloncore.engine.select_all_user")
def test_get_project_context_overview(mock_select_all):
    """Tests overview mode formats the raw database tuples into clean dictionaries."""
    
    # 1. Setup the fake data the database WOULD return
    # Tuple format based on your code: (name, timestamp, params_dict, results_dict, ..., status, id)
    # (name, timestamp, params, results, id, runtime, status)
    fake_runs = [
        ("run_alpha", "2026-04-01", {"lr": 0.01}, {"loss": 0.5}, "id_111", "00:01", "SUCCESS"),
        ("run_beta", "2026-04-02", {"lr": 0.02, "b": 32}, {}, "id_222", "00:02", "FAILED")
    ]
    fake_artifacts = ["id_111", "id_111"]
    
    mock_select_all.return_value = (fake_runs, fake_artifacts)
    
    # 2. Execute the engine logic
    # We can pass None for the engine because the DB call is mocked!
    result = get_project_context(engine=None)
    
    # 3. Assert the Engine transformed it correctly
    assert result["mode"] == "overview"
    assert len(result["runs"]) == 2
    
    # Check that run_alpha calculated assets and params correctly
    run_alpha_data = result["runs"][0]
    assert run_alpha_data["name"] == "run_alpha"
    assert run_alpha_data["param_count"] == 1
    assert run_alpha_data["asset_count"] == 3  # 1 result + 2 artifacts
    assert run_alpha_data["status"] == "SUCCESS"


@patch("silloncore.engine.select_key_user")
def test_get_project_context_specific(mock_select_key):
    """Tests specific mode safely extracts metadata and handles missing indices."""
    
    # Fake run with a language inside the metadata dict at index 4
    fake_runs = [
        ("run_target", "2026-04-03", {}, {}, {"sillon.language": "python 3.11"}, "id_333", "00:05:22", "KILLED")
    ]
    mock_select_key.return_value = (fake_runs, [])
    
    result = get_project_context(engine=None, run_names=["run_target"])
    
    assert result["mode"] == "specific"
    
    run_data = result["runs"][0]
    assert run_data["name"] == "run_target"
    assert run_data["language"] == "python 3.11"
    assert run_data["runtime"] == "00:05:22"
    assert run_data["status"] == "KILLED"


# ==========================================
#      TESTING GET_RUN_DETAILS
# ==========================================

@patch("silloncore.engine.select_param_user")
@patch("silloncore.engine.select_result_user")
def test_get_run_details_wildcards(mock_select_result, mock_select_param):
    """Tests that the '%all%' wildcard triggers the correct database routing."""
    
    mock_select_param.return_value = [{"fake": "param"}]
    mock_select_result.return_value = ([{"fake": "result"}], [{"fake": "artifact"}])
    
    # Requesting %all% for both
    out = get_run_details(engine=None, run_names=["run_1"], params=["%all%"], results=["%all%"])
    
    # Assert the correct branch of the if/else was taken (search_key should NOT be passed)
    mock_select_param.assert_called_once_with(None, search_id=["run_1"])
    mock_select_result.assert_called_once_with(None, search_id=["run_1"])
    
    assert "parameter" in out
    assert "result" in out
    assert "artifacts" in out


@patch("silloncore.engine.select_metadata_user")
def test_get_run_details_specific_keys(mock_select_metadata):
    """Tests that specific keys are passed down to the database layer properly."""
    
    out = get_run_details(engine=None, run_names=["run_2"], meta=["hostname", "os"])
    
    mock_select_metadata.assert_called_once_with(None, search_key=["hostname", "os"], search_id=["run_2"])


# ==========================================
#      TESTING ADD_METADATA_TO_RUNS
# ==========================================

def test_add_metadata_validation_empty_runs():
    """Tests that the engine catches missing run names before hitting the DB."""
    result = add_metadata_to_runs(engine=None, run_names=[])
    assert result["status"] == "error"
    assert "No run names provided" in result["message"]


def test_add_metadata_validation_empty_payload():
    """Tests that the engine catches missing payloads before hitting the DB."""
    result = add_metadata_to_runs(engine=None, run_names=["run_1"])
    assert result["status"] == "warning"
    assert "No notes, tags or metadata provided" in result["message"]


@patch("silloncore.engine.db_append_note_tag")
def test_add_metadata_db_failure(mock_db_append):
    """Tests error formatting when the database fails to find the requested runs."""
    # Database returns an empty list, meaning nothing was updated
    mock_db_append.return_value = []
    
    result = add_metadata_to_runs(engine=None, run_names=["ghost_run"], tags=["fail"])
    
    assert result["status"] == "error"
    assert "No runs found" in result["message"]


@patch("silloncore.engine.db_append_note_tag")
def test_add_metadata_success(mock_db_append):
    """Tests the success dictionary is formatted perfectly."""
    # Database successfully updates two runs
    mock_db_append.return_value = ["run_1", "run_2"]
    
    result = add_metadata_to_runs(
        engine=None, 
        run_names=["run_1", "run_2"], 
        notes=["A note"], 
        tags=["tag1", "tag2"]
    )
    
    assert result["status"] == "success"
    assert result["updated_count"] == 2
    assert result["added_notes"] == 1
    assert result["added_tags"] == 2
    assert result["updated_runs"] == ["run_1", "run_2"]
