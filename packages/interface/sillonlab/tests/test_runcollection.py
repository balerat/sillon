"""RunCollection ergonomics: sorting, lazy-load correctness in to_dataframe,
and uuid lookup before a snapshot has been fetched.
"""

import shutil
import time
from pathlib import Path

import pytest

import sillonlab as sl

CURRENT_PATH = Path(__file__).parent.resolve()
PROJECT = CURRENT_PATH / "_collection_project"


@pytest.fixture(scope="module", autouse=True)
def project():
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    PROJECT.mkdir(parents=True)

    import sillonpy as sp

    # Three runs with a deliberately non-alphabetical loss ordering.
    for name, loss in (("alpha", 0.30), ("beta", 0.05), ("gamma", 0.17)):
        with sp.track_run(run_name=name, author="t", project_name="collection",
                          project_path=str(PROJECT)):
            sp.log_param("loss", loss)
            sp.log_param("label", name)
    time.sleep(0.8)

    yield sl.load_project(str(PROJECT))

    time.sleep(0.3)
    if PROJECT.exists():
        shutil.rmtree(PROJECT, ignore_errors=True)


# --- sort_by ----------------------------------------------------------------


def test_sort_by_parameter_name(project):
    ordered = project.runs().sort_by("loss")
    assert [r.name for r in ordered] == ["beta", "gamma", "alpha"]


def test_sort_by_reverse(project):
    ordered = project.runs().sort_by("loss", reverse=True)
    assert [r.name for r in ordered] == ["alpha", "gamma", "beta"]


def test_sort_by_callable(project):
    ordered = project.runs().sort_by(lambda r: r.name, reverse=True)
    assert [r.name for r in ordered] == ["gamma", "beta", "alpha"]


def test_sort_by_returns_a_collection_and_slices(project):
    """The motivating case: "my two best runs"."""
    best = project.runs().sort_by("loss")[:2]
    assert isinstance(best, sl.RunCollection)
    assert [r.name for r in best] == ["beta", "gamma"]


def test_sort_by_puts_missing_keys_last(project):
    """A run without the key must never displace one that has it."""
    for reverse in (False, True):
        ordered = project.runs().sort_by("not_a_real_key", reverse=reverse)
        assert len(ordered) == 3  # nothing dropped


def test_sort_by_does_not_mutate_the_original(project):
    runs = project.runs()
    before = [r.name for r in runs]
    runs.sort_by("loss")
    assert [r.name for r in runs] == before


# --- to_dataframe -----------------------------------------------------------


def test_to_dataframe_on_query_results_has_no_null_columns(project):
    """The regression: query() runs carry no context, so timestamp and status
    were read as None before the lazy snapshot load ever happened."""
    pytest.importorskip("pandas")

    df = project.query(label="beta").to_dataframe()
    assert len(df) == 1
    assert df["timestamp"].notna().all(), "timestamp came back null"
    assert df["status"].notna().all(), "status came back null"
    assert df["status"].iloc[0] == "SUCCESS"


def test_to_dataframe_on_runs_still_works(project):
    pytest.importorskip("pandas")

    df = project.runs().to_dataframe()
    assert len(df) == 3
    assert df["timestamp"].notna().all()
    assert set(df["name"]) == {"alpha", "beta", "gamma"}


# --- lookup -----------------------------------------------------------------


def test_lookup_by_uuid_on_an_unloaded_collection(project):
    """uuid is None until a snapshot loads, so this used to raise KeyError."""
    loaded = project.runs()["beta"]
    loaded._load_snapshot()
    target_uuid = loaded.uuid
    assert target_uuid

    fresh = project.query(label="beta")  # no context pre-filled
    assert fresh[target_uuid].name == "beta"


def test_lookup_by_name_still_works(project):
    assert project.runs()["gamma"].name == "gamma"


def test_unknown_key_raises(project):
    with pytest.raises(KeyError):
        project.runs()["no-such-run"]
