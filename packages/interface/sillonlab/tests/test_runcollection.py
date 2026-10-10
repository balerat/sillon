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


AWKWARD = CURRENT_PATH / "_awkward_project"


@pytest.fixture(scope="module")
def awkward():
    """Values that are awkward to order, which is where sort_by came apart.

    A heavy array parameter (the database holds a reference, not the array), a
    parameter present on only some runs, and one logged as an int in one run
    and a string in another -- which is what happens when a value comes
    straight off `sys.argv` in some scripts and not others.
    """
    import numpy as np
    import sillonpy as sp

    if AWKWARD.exists():
        shutil.rmtree(AWKWARD)
    AWKWARD.mkdir(parents=True)

    for index, (name, mixed) in enumerate((("one", 1), ("two", "2"), ("three", 3))):
        with sp.track_run(run_name=name, author="t", project_name="awkward",
                          project_path=str(AWKWARD)):
            sp.log_param("big_param", np.arange(3000, dtype="float64") + index)
            sp.log_param("mixed", mixed)
            if index % 2 == 0:
                sp.log_param("only_some", index)
    time.sleep(0.8)

    yield sl.load_project(str(AWKWARD))

    time.sleep(0.3)
    if AWKWARD.exists():
        shutil.rmtree(AWKWARD, ignore_errors=True)


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


def test_sort_by_puts_missing_keys_last(awkward):
    """A run without the key must never displace one that has it.

    `only_some` is on two of the three runs, in both directions.
    """
    for reverse in (False, True):
        ordered = awkward.runs().sort_by("only_some", reverse=reverse)
        assert len(ordered) == 3                      # nothing dropped
        assert ordered[-1].name == "two"              # the one without it


def test_sort_by_a_key_nothing_has_is_an_error(project):
    """Not a quiet no-op.

    Returning the collection in the order it already had means a typo hands
    you the first runs you happened to log and lets you call them the best.
    """
    with pytest.raises(LookupError, match="no run in this collection has"):
        project.runs().sort_by("not_a_real_key")


def test_sort_by_a_heavy_array_parameter(awkward):
    """The database keeps a reference, not the array.

    Ordering the references is meaningless, and comparing them used to fail
    with `'<' not supported between instances of 'dict' and 'dict'`.
    """
    with pytest.raises(TypeError, match="cannot be compared"):
        awkward.runs().sort_by("big_param")


def test_sort_by_mixed_types_says_which(awkward):
    """Rather than numpy's or Python's own message, which names no key."""
    with pytest.raises(TypeError) as excinfo:
        awkward.runs().sort_by("mixed")
    message = str(excinfo.value)
    assert "mixed" in message
    assert "int" in message and "str" in message


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
