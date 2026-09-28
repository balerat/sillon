"""A run must be versioned by what its code does, end to end.

The question this answers: *"I fixed a sign error in September — which of my
runs used the fixed code?"* It has to survive the two obvious false positives
(a tuned constant, a new comment) and it has to notice a change inside the
user's **own library**, not just the entry script.
"""

import shutil
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

CURRENT_PATH = Path(__file__).parent.resolve()
PROJECT = CURRENT_PATH / "_codeversion_project"

HAM_BASE = "def hamiltonian(kinetic, potential):\n    return kinetic - potential\n"
RUN_SCRIPT = textwrap.dedent(
    """
    import sys
    import sillonpy as sp
    from lattice.ham import hamiltonian

    N = 5

    with sp.track_run(run_name=sys.argv[1], author="t", project_name="cv",
                      project_path=r"{project}"):
        sp.log_param("N", N)
        sp.log_result("h", float(hamiltonian(3.0, 1.0)))
    """
)


@pytest.fixture(scope="module", autouse=True)
def project():
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    (PROJECT / "lattice").mkdir(parents=True)
    (PROJECT / "lattice" / "__init__.py").write_text("")
    (PROJECT / "lattice" / "ham.py").write_text(HAM_BASE)
    (PROJECT / "run.py").write_text(RUN_SCRIPT.format(project=PROJECT))

    def _run(name):
        proc = subprocess.run(
            [sys.executable, "run.py", name],
            cwd=str(PROJECT), capture_output=True, text=True, timeout=90,
        )
        assert proc.returncode == 0, proc.stderr
        return proc

    # 1. baseline
    _run("base")
    # 2. a tuned constant only
    (PROJECT / "run.py").write_text(
        RUN_SCRIPT.format(project=PROJECT).replace("N = 5", "N = 4")
    )
    _run("tuned")
    # 3. a comment in the user's own library
    (PROJECT / "lattice" / "ham.py").write_text(HAM_BASE + "\n# a note to self\n")
    _run("commented")
    # 4. a real change, inside the user's own library
    (PROJECT / "lattice" / "ham.py").write_text(
        HAM_BASE.replace("kinetic - potential", "kinetic + potential")
    )
    _run("fixed")

    time.sleep(1)
    yield
    time.sleep(0.3)
    if PROJECT.exists():
        shutil.rmtree(PROJECT, ignore_errors=True)


def _versions():
    con = sqlite3.connect(PROJECT / ".sillon" / "database.sql")
    try:
        return dict(con.execute("SELECT name, logic_version FROM simulationtable"))
    finally:
        con.close()


# ==========================================
#            the core property
# ==========================================


def test_every_run_records_a_code_version():
    versions = _versions()
    assert set(versions) == {"base", "tuned", "commented", "fixed"}
    assert all(v for v in versions.values()), "a run was logged with no code version"


def test_a_tuned_constant_does_not_change_the_version():
    versions = _versions()
    assert versions["tuned"] == versions["base"]


def test_a_comment_in_my_own_library_does_not_change_the_version():
    versions = _versions()
    assert versions["commented"] == versions["base"]


def test_editing_my_own_library_does_change_the_version():
    """The whole point of covering custom modules, not just the entry script."""
    versions = _versions()
    assert versions["fixed"] != versions["base"]


# ==========================================
#          what it is usable for
# ==========================================


def test_runs_group_by_code_version():
    from silloncore.engine import get_code_versions
    from silloncore.project_paths import resolve_engine

    groups = get_code_versions(resolve_engine(PROJECT))
    assert len(groups) == 2

    by_size = sorted(groups, key=lambda g: g["run_count"], reverse=True)
    assert by_size[0]["run_count"] == 3
    assert set(by_size[0]["runs"]) == {"base", "tuned", "commented"}
    # base and tuned differ by a constant; commented does not add a third
    assert by_size[0]["constant_variants"] == 2


def test_the_file_map_names_which_module_changed():
    from silloncore.engine import get_code_version_files
    from silloncore.project_paths import resolve_engine

    engine = resolve_engine(PROJECT)
    versions = _versions()

    base = get_code_version_files(engine, versions["base"])["files"]
    fixed = get_code_version_files(engine, versions["fixed"])["files"]

    assert base["run.py"]["logic_hash"] == fixed["run.py"]["logic_hash"]
    assert base["lattice/ham.py"]["logic_hash"] != fixed["lattice/ham.py"]["logic_hash"]


def test_filtering_a_project_by_code_version():
    """`which runs used the fixed code` must be a query, not a scan."""
    import sillonlab as sl

    versions = _versions()
    project = sl.load_project(PROJECT)

    clean = project.query(fields={"logic_version": versions["fixed"]})
    assert sorted(r.name for r in clean) == ["fixed"]


def test_sources_are_stored_once_not_per_run():
    """Content addressing: 4 runs x 3 files must not be 12 copies."""
    stored = list((PROJECT / ".sillon" / "sources").iterdir())
    # main script (2 variants) + __init__ (1) + ham.py (3 variants) = 6
    assert len(stored) < 12
    assert len(stored) >= 4


def test_sillon_itself_is_not_part_of_the_users_code_version():
    """An editable sillon install must not land in the user's module list."""
    from silloncore.engine import get_code_version_files
    from silloncore.project_paths import resolve_engine

    files = get_code_version_files(resolve_engine(PROJECT), _versions()["base"])["files"]
    assert not any("sillon" in name for name in files), files
    assert set(files) == {"run.py", "lattice/__init__.py", "lattice/ham.py"}


# ==========================================
#          recovering old runs
# ==========================================


def test_backfill_recovers_versions_for_pre_feature_runs(tmp_path):
    """Runs logged before versioning existed still stored their entry script,
    so their version is recoverable — but only for that one file."""
    import json
    import sillonlab as sl
    from silloncore.engine import backfill_code_versions, get_code_versions
    from silloncore.project_paths import resolve_engine, resolve_storage_root

    db = PROJECT / ".sillon" / "database.sql"
    con = sqlite3.connect(db)
    try:
        con.execute("UPDATE simulationtable SET logic_version = NULL")
        for rid, meta in list(con.execute("SELECT id, meta_data FROM simulationtable")):
            m = json.loads(meta)
            m.pop("sillon.code.version", None)
            con.execute(
                "UPDATE simulationtable SET meta_data=? WHERE id=?", (json.dumps(m), rid)
            )
        con.commit()
    finally:
        con.close()

    engine = resolve_engine(PROJECT)
    assert all(v is None for v in _versions().values()), "setup failed"

    result = backfill_code_versions(engine, resolve_storage_root(PROJECT))
    assert result["updated"] == 4
    assert result["skipped"] == 0

    recovered = _versions()
    assert all(recovered.values()), "a run was left without a version"

    # Only the entry script is recoverable, so the ham.py change is invisible
    # here — and the group must say so rather than look like a full version.
    groups = get_code_versions(engine)
    assert all(g["partial"] for g in groups), "backfilled versions must be marked partial"
