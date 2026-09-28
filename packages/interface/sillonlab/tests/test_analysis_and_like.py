"""Analysis provenance, and finding runs like a given one.

Two small features that close gaps: a derived quantity should not lose its
origin the moment you compute it, and a project of 135 runs should be
navigable by "did I do something close to this?".
"""

import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

CURRENT_PATH = Path(__file__).parent.resolve()
PROJECT = CURRENT_PATH / "_analysis_like_project"


def _run(body: str, name: str = "tmp"):
    path = PROJECT / f"_{name}.py"
    path.write_text(textwrap.dedent(body).replace("{PROJECT}", str(PROJECT)))
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(PROJECT), capture_output=True, text=True, timeout=90,
        )
        assert proc.returncode == 0, proc.stderr
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture(scope="module", autouse=True)
def project():
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    PROJECT.mkdir(parents=True)

    _run("""
        import numpy as np, sillonpy as sp
        for degree in (1, 2, 3):
            for ridge in (0.0, 0.5):
                with sp.track_run(run_name=f"d{degree}_r{ridge}", author="t",
                                  project_name="al", project_path=r"{PROJECT}"):
                    sp.log_param({"degree": degree, "ridge": ridge,
                                  "seed": 7, "solver": "lstsq"})
                    sp.log_result("field", np.linspace(0, 1, 256))
                    sp.log_result("energy", float(degree))

        with sp.track_run(run_name="unrelated", author="t", project_name="al",
                          project_path=r"{PROJECT}"):
            sp.log_param({"degree": 2, "method": "bayes", "prior": "gauss"})
    """, "seed")
    time.sleep(1)

    import sillonlab as sl
    yield sl.load_project(PROJECT)
    time.sleep(0.3)
    if PROJECT.exists():
        shutil.rmtree(PROJECT, ignore_errors=True)


# ==========================================
#          ANALYSIS PROVENANCE
# ==========================================


def test_explicit_used_is_recorded(project):
    import numpy as np

    run = project.get("d1_r0.0")
    run.add_analysis("spectrum", np.abs(np.fft.rfft(run.load_result("field"))),
                     used=["field"], comment="magnitude only")

    meta = project.get("d1_r0.0").analyses["spectrum"]
    assert meta["used"] == ["field"]
    assert meta["comment"] == "magnitude only"


def test_a_single_string_is_accepted(project):
    run = project.get("d2_r0.0")
    run.add_analysis("scaled", [1, 2, 3], used="field")
    assert project.get("d2_r0.0").analyses["scaled"]["used"] == ["field"]


def test_used_is_inferred_from_what_was_loaded(project):
    """The analysis was computed from data you just loaded; sillon saw that."""
    import sillonlab as sl

    sl.forget_reads()
    run = project.get("d3_r0.0")
    data = run.load_result("field") * run.load_result("energy")
    run.add_analysis("inferred", data)

    meta = project.get("d3_r0.0").analyses["inferred"]
    assert meta["used"] == ["energy", "field"]


def test_explicit_used_beats_inference(project):
    import sillonlab as sl

    sl.forget_reads()
    run = project.get("d1_r0.5")
    run.load_result("field")
    run.load_result("energy")
    run.add_analysis("narrow", [1, 2], used=["energy"])

    assert project.get("d1_r0.5").analyses["narrow"]["used"] == ["energy"]


def test_no_reads_means_no_claimed_provenance(project):
    import sillonlab as sl

    sl.forget_reads()
    run = project.get("d2_r0.5")
    run.add_analysis("standalone", [1, 2, 3])
    assert project.get("d2_r0.5").analyses["standalone"]["used"] == []


def test_analysis_still_loads_back(project):
    import numpy as np

    run = project.get("d3_r0.5")
    run.add_analysis("roundtrip", np.arange(10, dtype=float), used=["field"])
    assert np.array_equal(
        project.get("d3_r0.5").load_analysis("roundtrip"), np.arange(10, dtype=float)
    )


# ==========================================
#              RESEMBLANCE
# ==========================================


def test_similar_runs_are_ranked_by_shared_configuration(project):
    matches = project.like("d1_r0.0")
    assert matches, "no matches returned"
    # the run sharing 3 of 4 parameters must beat the one sharing almost nothing
    names = [m["name"] for m in matches]
    assert names.index("d2_r0.0") < names.index("unrelated")
    assert matches[-1]["name"] == "unrelated"


def test_a_closer_value_ranks_above_a_further_one(project):
    """Structural overlap ties; the tiebreak is how much actually changed."""
    matches = {m["name"]: i for i, m in enumerate(project.like("d1_r0.0"))}
    assert matches["d2_r0.0"] < matches["d3_r0.0"]


def test_the_target_is_not_its_own_match(project):
    assert all(m["name"] != "d1_r0.0" for m in project.like("d1_r0.0"))


def test_changes_name_what_differs(project):
    match = next(m for m in project.like("d1_r0.0") if m["name"] == "d2_r0.0")
    assert match["changes"] == {"degree": (1, 2)}


def test_a_structurally_different_run_scores_low(project):
    match = next(m for m in project.like("d1_r0.0") if m["name"] == "unrelated")
    assert match["score"] < 0.3
    assert match["only_in_other"] and match["missing_here"]


def test_limit_is_respected(project):
    assert len(project.like("d1_r0.0", limit=2)) == 2


def test_a_run_object_is_accepted(project):
    assert project.like(project.get("d1_r0.0"), limit=1)


def test_a_missing_run_raises(project):
    with pytest.raises(LookupError):
        project.like("no_such_run")


def test_similarity_is_symmetric_and_bounded():
    from silloncore.diff import similarity

    a, b = {"x": 1, "y": 2}, {"x": 1, "z": 3}
    assert similarity(a, b)["score"] == similarity(b, a)["score"]
    assert 0.0 <= similarity(a, b)["score"] <= 1.0
    assert similarity({}, {})["score"] == 1.0
    assert similarity({"x": 1}, {"x": 1})["score"] == 1.0


# ==========================================
#              REPORT BUNDLES
# ==========================================


def test_report_dest_can_be_a_directory(project, tmp_path):
    """`--dest out/` must mean "put it in there", as it does for grab.

    Naming a directory used to raise IsADirectoryError, because the path was
    treated as the zip's filename.
    """
    out = tmp_path / "bundles"
    out.mkdir()

    written = project.get("d1_r0.0").report(out)
    assert written.is_file()
    assert written.parent == out
    assert written.name.endswith(".zip")


def test_report_dest_can_still_be_a_filename(project, tmp_path):
    written = project.get("d1_r0.0").report(tmp_path / "custom.zip")
    assert written.name == "custom.zip"
    assert written.is_file()


def test_report_bundle_is_self_contained(project, tmp_path):
    import zipfile

    written = project.get("d1_r0.0").report(tmp_path / "b.zip", with_data=True)
    names = zipfile.ZipFile(written).namelist()
    assert "manifest.json" in names
    assert "report.md" in names
    assert "data.hdf5" in names, "with_data=True must embed the results"
