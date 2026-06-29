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

def _index_entry(**overrides):
    """A select_run_index row with sensible defaults for the context tests."""
    entry = {
        "id": 1,
        "uuid": "uuid-x",
        "name": "run_x",
        "date": "2026-04-01",
        "status": "SUCCESS",
        "author": "",
        "hostname": "",
        "platform": "python",
        "runtime": "00:01",
        "sillonversion": "1.0.0",
        "parameters": {},
        "results": {},
        "result_names": [],
        "meta_data": {},
        "tag": [],
        "note": [],
        "hashes": {},
        "artifacts": [],
        "analyses": [],
        "figures": [],
    }
    entry.update(overrides)
    return entry


@patch("silloncore.engine.select_run_index")
def test_get_project_context_overview(mock_index):
    """Tests overview mode formats the run index into clean dictionaries."""
    mock_index.return_value = [
        _index_entry(
            name="run_alpha", uuid="id_111", date="2026-04-01",
            parameters={"lr": 0.01}, results={"loss": "loss"}, result_names=["loss"],
            artifacts=["a1", "a2"], status="SUCCESS",
        ),
        _index_entry(
            name="run_beta", uuid="id_222", date="2026-04-02",
            parameters={"lr": 0.02, "b": 32}, status="FAILED",
        ),
    ]

    result = get_project_context(engine=None)

    assert result["mode"] == "overview"
    assert len(result["runs"]) == 2

    run_alpha = next(r for r in result["runs"] if r["name"] == "run_alpha")
    assert run_alpha["param_count"] == 1
    assert run_alpha["asset_count"] == 3  # 1 result + 2 artifacts
    assert run_alpha["status"] == "SUCCESS"
    assert run_alpha["uuid"] == "id_111"


@patch("silloncore.engine.select_run_index")
def test_get_project_context_specific(mock_index):
    """Tests specific mode filters the index and extracts metadata."""
    mock_index.return_value = [
        _index_entry(
            name="run_target", uuid="id_333", date="2026-04-03",
            meta_data={"sillon.language": "python 3.11"}, runtime="00:05:22",
            status="KILLED",
        ),
        _index_entry(name="other", uuid="id_999"),
    ]

    result = get_project_context(engine=None, run_names=["run_target"])

    assert result["mode"] == "specific"
    assert len(result["runs"]) == 1
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
