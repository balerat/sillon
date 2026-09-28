"""Comparing runs must answer what changed, and whether it mattered.

Two questions, two modes: *"these two disagree, why?"* and *"what was this
sweep varying?"* — the second being what you need when you come back to a
folder of runs whose names mean nothing to you any more.
"""

import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

CURRENT_PATH = Path(__file__).parent.resolve()
PROJECT = CURRENT_PATH / "_diff_project"

HAM = "def hamiltonian(kinetic, potential):\n    return kinetic - potential\n"
SCRIPT = """
    import sys
    import numpy as np
    import sillonpy as sp
    from lattice.ham import hamiltonian

    N = 5

    with sp.track_run(run_name=sys.argv[1], author="t", project_name="diff",
                      project_path=r"{PROJECT}"):
        sp.log_param("degree", int(sys.argv[2]))
        sp.log_param("ridge", 0.0)
        sp.log_param("seed", 7)
        x = np.linspace(0, 10, 200)
        y = 0.5 * x ** 3 - 2 * x ** 2 + 3 * x
        coef = np.polyfit(x, y, int(sys.argv[2]))
        sp.log_result("coef", coef)
        sp.log_result("rmse", float(np.sqrt(np.mean((y - np.polyval(coef, x)) ** 2))))
        sp.log_result("field", np.linspace(0, 1, 2000) * N)
        sp.log_result("label", "unchanged")
"""


def _run(name, degree):
    proc = subprocess.run(
        [sys.executable, "run.py", name, str(degree)],
        cwd=str(PROJECT), capture_output=True, text=True, timeout=90,
    )
    assert proc.returncode == 0, proc.stderr


@pytest.fixture(scope="module", autouse=True)
def project():
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    (PROJECT / "lattice").mkdir(parents=True)
    (PROJECT / "lattice" / "__init__.py").write_text("")
    (PROJECT / "lattice" / "ham.py").write_text(HAM)
    script = textwrap.dedent(SCRIPT).replace("{PROJECT}", str(PROJECT))
    (PROJECT / "run.py").write_text(script)

    _run("alpha", 3)
    # same logic, one tuned constant
    (PROJECT / "run.py").write_text(script.replace("N = 5", "N = 4"))
    _run("beta", 5)
    # a genuine logic change, in the user's own library
    (PROJECT / "lattice" / "ham.py").write_text(
        HAM.replace("kinetic - potential", "kinetic + potential")
    )
    _run("gamma", 3)

    time.sleep(1)
    import sillonlab as sl
    yield sl.load_project(PROJECT)
    time.sleep(0.3)
    if PROJECT.exists():
        shutil.rmtree(PROJECT, ignore_errors=True)


# ==========================================
#               PARAMETERS
# ==========================================


def test_changed_parameters_carry_a_real_delta(project):
    """simple_compare used to return the string "N/A" where the delta belongs."""
    d = project.diff("alpha", "beta")
    degree = d["parameters"]["changed"]["degree"]
    assert degree["old"] == 3 and degree["new"] == 5
    assert degree["delta_pct"] == pytest.approx(66.67, abs=0.01)


def test_unchanged_parameters_are_counted_not_listed(project):
    d = project.diff("alpha", "beta")
    assert "seed" not in d["parameters"]["changed"]
    assert d["parameters"]["unchanged"] == 2  # ridge, seed


def test_no_percentage_where_it_would_be_meaningless(project):
    from silloncore.diff import percent_delta

    assert percent_delta(0, 5) is None          # undefined baseline
    assert percent_delta("a", "b") is None      # not numeric
    assert percent_delta(True, False) is None   # a bool percentage says nothing
    assert percent_delta(4, 2) == pytest.approx(-50.0)


# ==========================================
#                  CODE
# ==========================================


def test_a_tuned_constant_reads_as_same_logic(project):
    """The line you actually read: were these two runs comparable?"""
    d = project.diff("alpha", "beta")
    assert d["code"]["same_logic"] is True
    assert d["code"]["constants_differ"] is True
    assert d["code"]["files"]["run.py"]["status"] == "constants"
    assert d["code"]["files"]["lattice/ham.py"]["status"] == "same"


def test_a_logic_change_is_reported_as_such(project):
    d = project.diff("alpha", "gamma")
    assert d["code"]["same_logic"] is False
    assert d["code"]["files"]["lattice/ham.py"]["status"] == "changed"


def test_the_source_diff_shows_the_changed_file(project):
    d = project.diff("alpha", "gamma")
    source = d["code"]["source_diff"]
    assert "kinetic - potential" in source
    assert "kinetic + potential" in source
    assert "lattice/ham.py" in source


# ==========================================
#                 RESULTS
# ==========================================


def test_a_scalar_result_compares_numerically(project):
    """A logged scalar lands as a 0-d dataset; comparing it by hash would be
    true but useless."""
    d = project.diff("alpha", "beta")
    rmse = d["results"]["rmse"]
    assert rmse["status"] == "changed"
    assert rmse["delta_pct"] is not None
    assert rmse["old"]["kind"] == "scalar"


def test_a_shape_change_is_named_as_one(project):
    d = project.diff("alpha", "beta")
    coef = d["results"]["coef"]
    assert coef["status"] == "changed"
    assert coef["reason"] == "shape"
    assert coef["old"]["shape"] == (4,)
    assert coef["new"]["shape"] == (6,)


def test_same_shape_different_contents_is_distinguished(project):
    d = project.diff("alpha", "beta")
    field = d["results"]["field"]
    assert field["reason"] == "contents"
    assert field["old"]["shape"] == field["new"]["shape"]
    assert field["old"]["dtype"] == field["new"]["dtype"]


def test_identical_results_are_reported_as_unchanged(project):
    d = project.diff("alpha", "beta")
    assert d["results"]["label"]["status"] == "same"


def test_a_large_result_is_not_loaded_to_compare(project):
    """Above the threshold, shape and dtype are used and the diff says so
    rather than stalling on a gigabyte."""
    d = project.diff("alpha", "beta", max_bytes=8)
    field = d["results"]["field"]
    assert field["status"] == "unknown"
    assert field["reason"] == "too_large"
    assert field["old"]["compared"] is False
    # ...but what is known for free is still reported
    assert field["old"]["shape"] == (2000,)


def test_a_missing_run_raises(project):
    with pytest.raises(LookupError):
        project.diff("alpha", "no_such_run")


# ==========================================
#                  N-WAY
# ==========================================


def test_across_separates_varying_from_constant(project):
    across = project.diff_across(["alpha", "beta", "gamma"])
    assert across["run_count"] == 3
    assert sorted(across["varying"]) == ["degree"]
    assert across["constant"] == {"ridge": 0.0, "seed": 7}


def test_across_flags_when_runs_span_code_versions(project):
    """Two versions in one set means the comparison is not apples to apples."""
    across = project.diff_across(["alpha", "beta", "gamma"])
    assert len(across["logic_versions"]) == 2

    same_code = project.diff_across(["alpha", "beta"])
    assert len(same_code["logic_versions"]) == 1


def test_across_accepts_a_bare_string_filter(project):
    """has_tag="x" must behave the way people write it, not require a list."""
    assert project.diff_across(has_tag="nothing_tagged_this")["run_count"] == 0


def test_across_on_an_empty_set_is_not_an_error(project):
    across = project.diff_across([])
    assert across["run_count"] == 0
    assert across["varying"] == {} and across["constant"] == {}
