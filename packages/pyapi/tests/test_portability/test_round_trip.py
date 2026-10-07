"""Two real projects, one bundle, and every field compared.

The format tests build their fixtures by hand, which proves the plumbing but
not that the plumbing is connected to anything. This logs runs through the
actual client and daemon — heavy arrays offloaded to HDF5, a heavy *parameter*
(which `report --with-data` has never carried), an artifact copied off disk, a
figure with its provenance, automatic lineage, two code versions — then exports,
imports into a second project, and asserts the second project gives the same
answers as the first.

It also pins the thing that makes an import safe to run: the destination's own
work is never touched, even when its run has the same name as an incoming one.
"""

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

CURRENT_PATH = Path(__file__).parent.resolve()
ORIGIN = CURRENT_PATH / "_rt_origin"
DEST = CURRENT_PATH / "_rt_dest"
OUT = CURRENT_PATH / "_rt_out"

# A heavy parameter and a heavy result, an artifact, a figure, a tag and a note.
ORIGIN_SCRIPT = textwrap.dedent(
    """
    import sys
    import numpy as np
    import sillonpy as sp

    SCALE = 1.0

    deg = int(sys.argv[1])
    with sp.track_run(run_name=f"deg{deg}", author="doph", project_name="Origin",
                      project_path="."):
        sp.log_param("degree", deg)
        sp.log_param("solver", "lu")
        sp.log_param("grid", np.arange(2000, dtype="float64") * deg)
        sp.log_result("rmse", SCALE / deg)
        sp.log_result("field", np.arange(5000, dtype="float64") * deg)
        with open("mesh.txt", "w") as handle:
            handle.write(f"mesh for degree {deg}\\n")
        sp.log_result("mesh", path="mesh.txt", save_result=True)
        with open("fit.png", "wb") as handle:
            handle.write(b"\\x89PNG" + bytes([deg]) * 64)
        sp.log_figure(name="fit", path="fit.png", used=["degree", "rmse"],
                      caption=f"degree {deg}")
        sp.add_tag("sweep")
        sp.add_note("round trip")
    """
)

# A derived run: reads the parent through sillonlab, so lineage is automatic.
DERIVE_SCRIPT = textwrap.dedent(
    """
    import sillonlab as sl
    import sillonpy as sp

    parent = sl.load_project(".").get("deg3")
    coef = parent.load_result("field")

    with sp.track_run(run_name="refined", author="doph", project_name="Origin",
                      project_path="."):
        sp.log_param("degree", 3)
        sp.log_result("rmse", float(coef.mean()))
    """
)

DEST_SCRIPT = textwrap.dedent(
    """
    import sillonpy as sp

    with sp.track_run(run_name="deg3", author="someone-else",
                      project_name="Destination", project_path="."):
        sp.log_param("degree", 99)
        sp.log_result("rmse", 0.5)
    """
)


def _run_script(project: Path, body: str, *args, name="run.py"):
    (project / name).write_text(body)
    proc = subprocess.run(
        [sys.executable, name, *[str(a) for a in args]],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "SILLON_IDLE_TIMEOUT": "2.0"},
    )
    assert proc.returncode == 0, proc.stderr
    return proc


@pytest.fixture(scope="module")
def projects():
    for path in (ORIGIN, DEST, OUT):
        shutil.rmtree(path, ignore_errors=True)
    ORIGIN.mkdir(parents=True)
    DEST.mkdir(parents=True)
    OUT.mkdir(parents=True)

    for degree in (2, 3):
        _run_script(ORIGIN, ORIGIN_SCRIPT, degree)
    # A second code version: the same logic, a different tuned constant plus a
    # changed expression, so `versions` has something to group.
    _run_script(ORIGIN, ORIGIN_SCRIPT.replace("SCALE / deg", "SCALE / (deg + 1)"), 4)
    _run_script(ORIGIN, DERIVE_SCRIPT, name="derive.py")

    _run_script(DEST, DEST_SCRIPT, name="seed.py")

    yield
    for path in (ORIGIN, DEST, OUT):
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="module")
def bundle(projects):
    import sillonlab as sl

    result = sl.load_project(ORIGIN).export(dest=OUT)
    assert result["skipped_data"] == [], result["skipped_data"]
    return result["path"]


@pytest.fixture(scope="module")
def imported(bundle):
    import sillonlab as sl

    result = sl.load_project(DEST).import_from(bundle)
    assert result["imported"] == 4, result
    return result


def _origin():
    import sillonlab as sl

    return sl.load_project(ORIGIN)


def _dest():
    import sillonlab as sl

    return sl.load_project(DEST)


# ==========================================
#                 THE EXPORT
# ==========================================
def test_the_bundle_holds_every_run(bundle):
    from silloncore.engine import inspect_bundle

    described = inspect_bundle(bundle)
    assert described["run_count"] == 4
    assert described["has_data"] is True
    assert described["project_name"] == "Origin"
    assert {r["name"] for r in described["runs"]} == {"deg2", "deg3", "deg4", "refined"}


# ==========================================
#              FULL FIDELITY
# ==========================================
def test_every_field_survives(imported):
    """Each value compared against the origin, not against a literal."""
    src = _origin().get("deg3")
    dst = _dest().get("deg3~" + src.manifest()["hostname"])

    assert dst.uuid == src.uuid
    assert dst.timestamp == src.timestamp
    assert dst.status == src.status
    assert dst.parameters == src.parameters
    assert dst.tags == src.tags
    assert dst.notes == src.notes
    assert dst.figures == src.figures


def test_the_heavy_data_survives(imported):
    src = _origin().get("deg3")
    dst = _dest().get("deg3~" + src.manifest()["hostname"])

    assert np.array_equal(dst.load_result("field"), src.load_result("field"))
    assert dst.load_result("rmse") == src.load_result("rmse")
    # A heavy *parameter*, which a report has never carried.
    assert np.array_equal(dst.load_parameter("grid"), src.load_parameter("grid"))


def test_the_artifact_and_figure_bytes_survive(imported):
    src = _origin().get("deg3")
    dst = _dest().get("deg3~" + src.manifest()["hostname"])

    assert dst.load_artifact("mesh").read_bytes() == src.load_artifact("mesh").read_bytes()
    assert dst.load_figure("fit").read_bytes() == src.load_figure("fit").read_bytes()


def test_the_code_and_its_source_text_survive(imported):
    src = _origin().get("deg3")
    dst = _dest().get("deg3~" + src.manifest()["hostname"])

    assert dst.load_source() == src.load_source()
    src_version = src.manifest()["metadata"]["sillon.code.version"]
    dst_version = dst.manifest()["metadata"]["sillon.code.version"]
    assert dst_version == src_version


def test_the_version_that_wrote_the_run_is_preserved(imported):
    """Not the version doing the importing."""
    src = _origin().get("deg3")
    dst = _dest().get("deg3~" + src.manifest()["hostname"])
    assert dst.manifest()["sillonversion"] == src.manifest()["sillonversion"]


def test_code_versions_group_the_same_way_in_both(imported):
    origin_groups = {
        v["logic_version"]: v["run_count"] for v in _origin().versions() if v["logic_version"]
    }
    dest_groups = {
        v["logic_version"]: v["run_count"] for v in _dest().versions() if v["logic_version"]
    }
    assert len(origin_groups) >= 2, "the fixture did not produce two code versions"
    # Every origin version came across with the same number of runs behind it.
    for version, count in origin_groups.items():
        assert dest_groups.get(version) == count, version


def test_diff_gives_the_same_answer_in_both(imported):
    host = _origin().get("deg3").manifest()["hostname"]
    here = _origin().diff("deg2", "deg3")
    there = _dest().diff(f"deg2", f"deg3~{host}")

    assert here["parameters"]["changed"].keys() == there["parameters"]["changed"].keys()
    assert here["code"]["same_logic"] == there["code"]["same_logic"]
    assert set(here["results"]) == set(there["results"])


# ==========================================
#                  LINEAGE
# ==========================================
def test_automatic_lineage_crosses_the_bundle(imported):
    """`refined` read `deg3`, so the edge was recorded without `inherit=`."""
    host = _origin().get("deg3").manifest()["hostname"]
    assert _origin().get("refined").parent_links(), "no lineage in the origin"

    parent = _dest().get("refined").parents()[0]
    assert parent.name == f"deg3~{host}"
    assert parent.parameters["degree"] == 3


def test_the_destination_namesake_is_not_mistaken_for_the_parent(imported):
    """The edge's cached name is "deg3", which locally belongs to another run."""
    assert _dest().get("deg3").parameters["degree"] == 99
    assert len(_dest().get("deg3").children()) == 0


# ==========================================
#          THE DESTINATION IS SAFE
# ==========================================
def test_local_work_is_untouched(imported):
    local = _dest().get("deg3")
    assert local.parameters["degree"] == 99
    assert local.load_result("rmse") == 0.5
    assert local.manifest()["author"] == "someone-else"


def test_importing_again_is_a_no_op(bundle, imported):
    before = {r.name for r in _dest().runs()}
    again = _dest().import_from(bundle)
    assert again["imported"] == 0
    assert len(again["already_here"]) == 4
    assert {r.name for r in _dest().runs()} == before


def test_the_destination_has_exactly_what_it_should(imported):
    host = _origin().get("deg3").manifest()["hostname"]
    assert {r.name for r in _dest().runs()} == {
        "deg3",                 # its own
        "deg2",
        f"deg3~{host}",         # renamed on the way in
        "deg4",
        "refined",
    }
