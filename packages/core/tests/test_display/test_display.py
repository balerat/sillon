"""Smoke tests for the renderers in silloncore.display.

These are pure functions of a payload the engine already built, so the only
thing that can really go wrong is that one of them blows up on a shape it is
meant to handle. That is exactly how 2.0.0 shipped a landing view which crashed
on any project without a recorded name: a missing `pathlib` import on the
fallback branch, never rendered in testing because every project we tried had a
name.

So each renderer is called here on the shapes the engine produces -- including
the empty ones and the ones that take the quiet branch -- with the output sent
to a throwaway console, so a broken row fails the suite instead of decorating
someone's terminal.
"""

import io

import pytest
from rich.console import Console

from silloncore import display


# Wide enough that no column is ellipsized, so an assertion about content is
# about content and not about wrapping. A narrow terminal gets its own test.
WIDTH = 200


@pytest.fixture(autouse=True)
def quiet_console(monkeypatch):
    """Render into a string buffer, and hand it back so tests can look."""
    buffer = io.StringIO()
    monkeypatch.setattr(display, "console", Console(file=buffer, width=WIDTH))
    return buffer


@pytest.fixture
def narrow_console(monkeypatch):
    """A cramped terminal, where the fold/ratio columns have to give way."""
    buffer = io.StringIO()
    monkeypatch.setattr(display, "console", Console(file=buffer, width=48))
    return buffer


# ==========================================
#              THE LANDING VIEW
# ==========================================
def _summary(**over):
    """A `get_project_summary` payload."""
    base = {
        "name": "Shaking Lattice",
        "path": "/Users/doph/Code/phd/projects/shaking",
        "run_count": 135,
        "last_activity": "2026-09-01-10:00:00",
        "status_counts": {"SUCCESS": 132, "CRASHED": 3},
        "versions": 2,
        "current_version": "c8d01234deadbeef",
        "partial_versions": False,
        "bytes": 1_400_000_000,
        "daemon_running": True,
    }
    base.update(over)
    return base


def test_landing_with_a_named_project(quiet_console):
    display.print_landing(_summary(), "2.0.0")
    out = quiet_console.getvalue()
    assert "Shaking Lattice" in out
    assert "2.0.0" in out
    assert "132 ok" in out


def test_landing_without_a_project_name(quiet_console):
    """A project initialised before 2.0 has no name in its config.

    `resolve_project_name` returns "" for it, and the view falls back to the
    directory name. This is the path that crashed in 2.0.0.
    """
    display.print_landing(_summary(name=""), "2.0.0")
    assert "shaking" in quiet_console.getvalue()


def test_landing_on_an_empty_project(quiet_console):
    """Freshly initialised: no runs, no versions, no data, no daemon."""
    display.print_landing(
        _summary(
            name="",
            run_count=0,
            last_activity=None,
            status_counts={},
            versions=0,
            current_version=None,
            bytes=0,
            daemon_running=False,
        ),
        "2.0.0",
    )
    out = quiet_console.getvalue()
    assert "never" in out
    assert "not versioned" in out
    assert "daemon idle" in out


def test_landing_with_partial_versions_and_running_runs(quiet_console):
    display.print_landing(
        _summary(
            versions=1,
            partial_versions=True,
            status_counts={"SUCCESS": 4, "RUNNING": 1, "KILLED": 2, "FAILED": 1},
        ),
        "2.0.0",
    )
    out = quiet_console.getvalue()
    assert "1 version " in out or "1 version\n" in out
    assert "3 crashed" in out  # KILLED + FAILED, counted together
    assert "1 running" in out


def test_landing_outside_a_project(quiet_console):
    display.print_landing_outside_project("2.0.0")
    out = quiet_console.getvalue()
    assert "not inside a sillon project" in out
    assert "sillon projects" in out


# ==========================================
#                  THE RUNS
# ==========================================
def _run(**over):
    base = {
        "uuid": "a3f9c8d0-0000-0000-0000-000000000000",
        "name": "my_fit",
        "timestamp": "2026-09-01-10:00:00",
        "param_count": 4,
        "asset_count": 2,
        "status": "SUCCESS",
        "runtime": "0:00:03",
        "language": "python",
    }
    base.update(over)
    return base


def test_print_context_overview(quiet_console):
    display.print_context({"mode": "overview", "runs": []}, project_name="")
    display.print_context(
        {"mode": "overview", "runs": [_run(), _run(name="other", status="CRASHED")]},
        project_name="Shaking Lattice",
    )
    assert "my_fit" in quiet_console.getvalue()


def test_print_context_specific(quiet_console):
    display.print_context({"mode": "specific", "runs": [_run()]})
    assert "my_fit" in quiet_console.getvalue()


def test_print_projects(quiet_console):
    display.print_projects([])
    display.print_projects(
        [
            {
                "project_name": "Shaking Lattice",
                "project_path": "/Users/doph/Code/phd/projects/shaking",
                "run_count": 135,
                "last_activity": "2026-09-01-10:00:00",
                "exists": True,
            },
            {
                "project_name": "",
                "project_path": "/gone",
                "run_count": None,
                "last_activity": None,
                "exists": False,
            },
        ]
    )
    out = quiet_console.getvalue()
    assert "(unnamed)" in out
    assert "--prune" in out  # the hint, because one is missing


# ==========================================
#              CODE VERSIONS
# ==========================================
def test_print_code_versions(quiet_console):
    display.print_code_versions([])
    display.print_code_versions(
        [
            {
                "logic_version": "c8d01234deadbeef",
                "run_count": 12,
                "constant_variants": 3,
                "first_seen": "2026-08-01-10:00:00",
                "last_seen": "2026-09-01-10:00:00",
                "partial": False,
            },
            {
                "logic_version": "4756b7f9deadbeef",
                "run_count": 1,
                "constant_variants": 1,
                "first_seen": None,
                "last_seen": None,
                "partial": True,
            },
            # The bucket of runs logged before code versioning existed.
            {"logic_version": None, "run_count": 7, "constant_variants": 0},
        ]
    )
    out = quiet_console.getvalue()
    assert "entry script only" in out
    assert "before code versioning" in out


def test_print_code_version_files(quiet_console):
    display.print_code_version_files(
        {
            "logic_version": "c8d01234deadbeef",
            "run_count": 12,
            "files": {
                "run.py": {
                    "source_hash": "aaaa1111bbbb2222",
                    "ast_hash": "cccc3333dddd4444",
                    "logic_hash": "eeee5555ffff6666",
                },
                "mylib/solver.py": {"logic_hash": "1111222233334444"},
            },
        }
    )
    out = quiet_console.getvalue()
    assert "mylib/solver.py" in out
    assert "12 run(s)" in out


# ==========================================
#                  DIFF
# ==========================================
def _diff(**over):
    base = {
        "runs": [{"name": "baseline"}, {"name": "refined"}],
        "parameters": {"changed": {}, "added": [], "removed": [], "unchanged": 6},
        "code": {
            "known": True,
            "same_logic": True,
            "constants_differ": [],
            "logic_version": ("4756b7f9deadbeef", "4756b7f9deadbeef"),
            "files": {"run.py": {"status": "same"}},
        },
        "results": {},
        "context": {"status": None, "runtime": None},
    }
    base.update(over)
    return base


def test_print_diff_nothing_differs(quiet_console):
    display.print_diff(_diff())
    out = quiet_console.getvalue()
    assert "Parameters are identical." in out
    assert "same logic" in out


def test_print_diff_cosmetic_code_change(quiet_console):
    display.print_diff(
        _diff(code={
            "known": True,
            "same_logic": True,
            "constants_differ": [],
            "logic_version": ("4756b7f9deadbeef", "4756b7f9deadbeef"),
            "files": {"run.py": {"status": "cosmetic"}},
        })
    )
    assert "comments or formatting only" in quiet_console.getvalue()


def test_print_diff_unrecorded_code(quiet_console):
    display.print_diff(
        _diff(code={"known": False, "same_logic": None, "constants_differ": [],
                    "logic_version": (None, None), "files": {}})
    )
    assert "not recorded" in quiet_console.getvalue()


def test_print_diff_everything_differs(quiet_console):
    display.print_diff(
        _diff(
            parameters={
                "changed": {
                    "degree": {"old": 3, "new": 5, "delta_pct": 66.67},
                    "solver": {"old": "lu", "new": "qr", "delta_pct": None},
                    "huge": {"old": 1, "new": 100000, "delta_pct": 9999900.0},
                },
                "added": ["ridge"],
                "removed": ["damping"],
                "unchanged": 3,
            },
            code={
                "known": True,
                "same_logic": True,
                "constants_differ": ["run.py"],
                "logic_version": ("4756b7f9deadbeef", "4756b7f9deadbeef"),
                "files": {"run.py": {"status": "constants"}},
            },
            results={
                "rmse": {
                    "status": "changed", "reason": "value", "delta_pct": -37.11,
                    "old": {"kind": "scalar", "value": 9.7456},
                    "new": {"kind": "scalar", "value": 6.1295},
                },
                "coef": {
                    "status": "changed", "reason": "shape", "delta_pct": None,
                    "old": {"kind": "array", "dtype": "float64", "shape": [4]},
                    "new": {"kind": "array", "dtype": "float64", "shape": [6]},
                },
                "field": {
                    "status": "changed", "reason": "contents", "delta_pct": None,
                    "old": {"kind": "array", "dtype": "float64", "shape": [5000]},
                    "new": {"kind": "array", "dtype": "float64", "shape": [5000]},
                },
                "trace": {
                    "status": "unknown", "reason": "too_large", "delta_pct": None,
                    "old": {"kind": "array", "dtype": "float64", "shape": [10**9]},
                    "new": {"kind": "array", "dtype": "float64", "shape": [10**9]},
                },
                "history": {
                    "status": "changed", "reason": "contents", "delta_pct": None,
                    "old": {"kind": "sequence", "length": 3},
                    "new": {"kind": "mapping", "length": 2},
                },
                "extra": {"status": "added", "reason": None, "delta_pct": None,
                          "old": None, "new": {"kind": "scalar", "value": 1}},
                "gone": {"status": "removed", "reason": None, "delta_pct": None,
                         "old": {"kind": "scalar", "value": 1}, "new": None},
                "stable": {"status": "same", "reason": None, "delta_pct": None,
                           "old": None, "new": None},
            },
            context={"status": ("SUCCESS", "CRASHED"), "runtime": ("0:00:03", "0:01:40")},
        )
    )
    out = quiet_console.getvalue()
    assert "constants differ in run.py" in out
    assert "shape changed" in out
    assert "contents differ" in out
    assert "too large to compare" in out
    assert "CRASHED" in out


def test_print_diff_logic_changed(quiet_console):
    display.print_diff(
        _diff(code={
            "known": True,
            "same_logic": False,
            "constants_differ": [],
            "logic_version": ("4756b7f9deadbeef", "98167c00deadbeef"),
            "files": {"run.py": {"status": "changed"}, "new.py": {"status": "added"}},
        })
    )
    out = quiet_console.getvalue()
    assert "logic changed" in out
    assert "run.py" in out


def test_print_diff_identical_results(quiet_console):
    display.print_diff(
        _diff(results={"rmse": {"status": "same", "reason": None, "delta_pct": None,
                                "old": None, "new": None}})
    )
    assert "Results are identical." in quiet_console.getvalue()


def test_print_source_diff(quiet_console):
    display.print_source_diff("--- a/run.py\n+++ b/run.py\n@@ -1 +1 @@\n-N = 5\n+N = 4\n")
    display.print_source_diff("")


# ==========================================
#            DIFF ACROSS A SET
# ==========================================
def test_print_diff_across_nothing_matched(quiet_console):
    display.print_diff_across(
        {"run_count": 0, "varying": {}, "constant": [], "logic_versions": []}
    )
    assert "No runs matched." in quiet_console.getvalue()


def test_print_diff_across_a_sweep(quiet_console):
    display.print_diff_across(
        {
            "run_count": 10,
            "varying": {"degree": [1, 2, 3, 4, 5], "ridge": [0.0, 0.1]},
            "constant": ["seed", "solver"],
            "logic_versions": ["98167c00deadbeef"],
        }
    )
    out = quiet_console.getvalue()
    assert "one version" in out
    assert "seed, solver" in out


def test_print_diff_across_many_values_and_versions(quiet_console):
    """More values than fit, and a set spanning several code versions."""
    display.print_diff_across(
        {
            "run_count": 20,
            "varying": {"degree": list(range(12))},
            "constant": [],
            "logic_versions": ["98167c00deadbeef", "4756b7f9deadbeef"],
        }
    )
    out = quiet_console.getvalue()
    assert "12 values" in out
    assert "not all comparable" in out


def test_print_diff_across_identical_runs(quiet_console):
    display.print_diff_across(
        {"run_count": 3, "varying": {}, "constant": ["seed"], "logic_versions": []}
    )
    assert "every parameter is identical" in quiet_console.getvalue()


# ==========================================
#               RESEMBLANCE
# ==========================================
def test_print_similar_runs_nothing_to_compare(quiet_console):
    display.print_similar_runs({"run": "happy_perlman", "matches": []})
    assert "No other runs" in quiet_console.getvalue()


def test_print_similar_runs(quiet_console):
    display.print_similar_runs(
        {
            "run": "happy_perlman",
            "matches": [
                {
                    "name": "d2_r0.0", "score": 0.75, "same_code": True,
                    "changes": {"degree": (3, 2)},
                    "only_in_other": [], "missing_here": [],
                },
                {
                    # More changes than the four the table shows.
                    "name": "d4_r0.1", "score": 0.5, "same_code": True,
                    "changes": {f"k{i}": (i, i + 1) for i in range(6)},
                    "only_in_other": ["extra"], "missing_here": ["damping"],
                },
                {
                    # Nothing shared differs, but the runs are not the same
                    # thing either -- "identical parameters" would be a lie.
                    "name": "unrelated", "score": 0.17, "same_code": False,
                    "changes": {},
                    "only_in_other": ["a", "b"], "missing_here": ["c"],
                },
                {
                    "name": "rerun", "score": 1.0, "same_code": True,
                    "changes": {}, "only_in_other": [], "missing_here": [],
                },
            ],
        }
    )
    out = quiet_console.getvalue()
    assert "75%" in out
    assert "different parameter set" in out
    assert "identical parameters" in out
    assert "+1 extra" in out


# ==========================================
#             A NARROW TERMINAL
# ==========================================
def test_everything_renders_on_a_cramped_terminal(narrow_console):
    """The busiest views at 48 columns.

    Content gets ellipsized here, which is fine -- what matters is that the
    fold/ratio columns and the panels do not raise on the way.
    """
    display.print_landing(_summary(), "2.0.0")
    display.print_landing_outside_project("2.0.0")
    display.print_context({"mode": "overview", "runs": [_run()]}, project_name="P")
    display.print_context({"mode": "specific", "runs": [_run()]})
    display.print_projects(
        [{"project_name": "P", "project_path": "/a/very/long/path/to/a/project",
          "run_count": 1, "last_activity": "2026-09-01-10:00:00", "exists": True}]
    )
    display.print_code_versions(
        [{"logic_version": "c8d01234deadbeef", "run_count": 1, "constant_variants": 1,
          "first_seen": None, "last_seen": None, "partial": True}]
    )
    display.print_diff(_diff())
    display.print_diff_across(
        {"run_count": 2, "varying": {"degree": [1, 2]}, "constant": ["seed"],
         "logic_versions": ["98167c00deadbeef"]}
    )
    display.print_similar_runs(
        {"run": "r", "matches": [{"name": "s", "score": 0.5, "same_code": True,
                                  "changes": {"degree": (3, 2)},
                                  "only_in_other": [], "missing_here": []}]}
    )
    assert narrow_console.getvalue()


# ==========================================
#            WIDTH ON A WIDE TERMINAL
# ==========================================
def _widest(buffer):
    return max((len(line) for line in buffer.getvalue().splitlines()), default=0)


@pytest.fixture
def wide_console(monkeypatch):
    """A 200-column terminal, where stretching to fit looks absurd."""
    buffer = io.StringIO()
    monkeypatch.setattr(display, "console", Console(file=buffer, width=200))
    return buffer


def test_panels_size_to_their_content_not_to_the_terminal(wide_console):
    """A handful of short columns should not be spread across 200 columns."""
    display.print_landing(_summary(), "2.0.1")
    assert _widest(wide_console) < 100


def test_tables_size_to_their_content_not_to_the_terminal(wide_console):
    display.print_code_versions(
        [{"logic_version": "c8d01234deadbeef", "run_count": 1, "constant_variants": 1,
          "first_seen": None, "last_seen": None, "partial": False}]
    )
    assert _widest(wide_console) < 120


def test_a_section_rule_stays_a_separator(wide_console):
    """The one element with no content to measure, so it is capped instead."""
    display.print_diff(_diff())
    assert _widest(wide_console) <= display.MAX_RULE_WIDTH


def test_wide_content_still_gets_the_room_it_needs(wide_console):
    """Content-sizing cuts both ways: a long path must not be folded away."""
    path = "/Users/doph/Code/phd/projects/a-rather-deeply-nested/shaking-lattice"
    display.print_projects(
        [{"project_name": "Shaking Lattice", "project_path": path,
          "run_count": 135, "last_activity": "2026-09-01-10:00:00", "exists": True}]
    )
    assert path in wide_console.getvalue()
