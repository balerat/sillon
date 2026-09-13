"""Large arrays must not accumulate in the daemon's memory.

Staged arrays used to be read back with `f["data"][()]`, queued in
`Glob.results` until dump, and hashed with `pickle.dumps` -- so the daemon held
the whole array (twice, transiently) for the lifetime of the run, while the
staging file it came from had already been deleted. Staging protected the
client's memory, not the daemon's.
"""

import shutil
import time
from pathlib import Path

import numpy as np
import pytest

from silloncommon.hashing import get_hash
from silloncommon.socket_path import get_pidfile_path

CURRENT_PATH = Path(__file__).parent.resolve()
PROJECT = CURRENT_PATH / "_mem_project"

# Big enough that holding several would be obvious, small enough to stay quick.
ARRAY_MB = 24
ELEMENTS = ARRAY_MB * 1024 * 1024 // 8
N_ARRAYS = 6


@pytest.fixture(autouse=True)
def clean_project():
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    PROJECT.mkdir(parents=True)
    yield
    time.sleep(0.5)
    if PROJECT.exists():
        shutil.rmtree(PROJECT, ignore_errors=True)


def _daemon_rss_mb():
    psutil = pytest.importorskip("psutil")
    pid = int(get_pidfile_path(str(PROJECT)).read_text().strip())
    return psutil.Process(pid).memory_info().rss / (1024 * 1024)


def test_daemon_memory_does_not_grow_with_logged_arrays():
    psutil = pytest.importorskip("psutil")
    import sillonpy as sp

    with sp.track_run(run_name="mem", author="t", project_name="mem",
                      project_path=str(PROJECT)):
        sp.log_result("warmup", np.zeros(ELEMENTS))
        time.sleep(0.3)
        baseline = _daemon_rss_mb()

        for i in range(N_ARRAYS):
            sp.log_result(f"field_{i}", np.full(ELEMENTS, float(i)))

        time.sleep(0.3)
        after = _daemon_rss_mb()

    growth = after - baseline
    # Buffering would cost ~N_ARRAYS * ARRAY_MB (144 MB here). Allow generous
    # slack for allocator noise while still failing loudly on a regression.
    assert growth < ARRAY_MB * 2, (
        f"daemon grew {growth:.0f} MB over {N_ARRAYS} x {ARRAY_MB} MB arrays "
        "- staged data is being held in memory again"
    )


def test_streamed_array_round_trips_exactly():
    """Streaming the claim must not alter the data."""
    import sillonpy as sp
    import sillonlab as sl

    expected = np.linspace(0, 1, ELEMENTS)
    with sp.track_run(run_name="roundtrip", author="t", project_name="mem",
                      project_path=str(PROJECT)):
        sp.log_result("field", expected)
        sp.log_param("grid", expected)

    time.sleep(0.5)
    run = sl.load_project(str(PROJECT)).get("roundtrip")
    assert np.array_equal(run.load_result("field"), expected)
    assert np.array_equal(run.load_parameter("grid"), expected)


def test_staged_hash_matches_an_inline_hash(tmp_path):
    """A digest must not depend on which transport the value took.

    The client hashes before staging so the daemon never has to load the array
    to hash it -- but it must use the same function, or a staged array and an
    identical inline one would get different digests and stop comparing equal.
    """
    from silloncommon.hdf5_staging import write_staging_array

    value = np.arange(ELEMENTS, dtype=np.float64)
    pointer = write_staging_array(value, tmp_path)

    assert pointer["hash"] == get_hash(value)
    assert pointer["shape"] == [ELEMENTS]
    assert pointer["dtype"] == "float64"
