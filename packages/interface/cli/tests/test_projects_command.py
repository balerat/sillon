"""`sillon projects` / `sillonlab.list_projects` — the machine-wide listing."""

from pathlib import Path

import pytest

from silloncommon import registry
import silloncore.projects as projects_engine


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "user_config_dir", lambda: tmp_path / "config")
    return tmp_path


def _register(tmp_path, folder, name):
    d = tmp_path / folder
    (d / ".sillon").mkdir(parents=True)
    registry.upsert(f"id-{folder}", d, name, d / ".sillon", d / ".sillon")
    return d


def test_lists_registered_projects(isolated_registry, tmp_path):
    _register(tmp_path, "alpha", "Alpha Study")
    _register(tmp_path, "beta", "Beta Study")

    records = projects_engine.get_projects(with_stats=False)
    names = {r["project_name"] for r in records}
    assert names == {"Alpha Study", "Beta Study"}
    assert all(r["project_path"] for r in records), "the location is the point"


def test_missing_project_is_listed_but_flagged(isolated_registry, tmp_path):
    _register(tmp_path, "here", "Here")
    gone = tmp_path / "gone"
    registry.upsert("id-gone", gone, "Gone", gone / ".sillon", gone / ".sillon")

    records = projects_engine.get_projects(with_stats=False)
    by_name = {r["project_name"]: r for r in records}
    assert by_name["Here"]["exists"] is True
    assert by_name["Gone"]["exists"] is False

    # ...and can be excluded on request
    only_live = projects_engine.get_projects(include_missing=False, with_stats=False)
    assert [r["project_name"] for r in only_live] == ["Here"]


def test_unreadable_project_does_not_break_the_listing(isolated_registry, tmp_path):
    """A project dir with no database must not raise for the others."""
    _register(tmp_path, "good", "Good")
    _register(tmp_path, "empty", "Empty")  # .sillon exists but holds no database

    records = projects_engine.get_projects(with_stats=True)
    assert len(records) == 2
    assert all(r["run_count"] is None or isinstance(r["run_count"], int) for r in records)


def test_find_project_by_name_and_prefix(isolated_registry, tmp_path):
    target = _register(tmp_path, "shaking", "Shaking Lattice Study")
    _register(tmp_path, "other", "Thermal Sweep")

    assert projects_engine.find_project("Shaking Lattice Study")["project_path"] == str(target.resolve())
    assert projects_engine.find_project("shaking lattice")["project_path"] == str(target.resolve())
    assert projects_engine.find_project(str(target))["project_path"] == str(target.resolve())
    assert projects_engine.find_project("nothing like this") is None


def test_find_project_refuses_an_ambiguous_prefix(isolated_registry, tmp_path):
    _register(tmp_path, "s1", "Sweep One")
    _register(tmp_path, "s2", "Sweep Two")
    assert projects_engine.find_project("Sweep") is None


def test_prune_drops_dead_entries(isolated_registry, tmp_path):
    _register(tmp_path, "live", "Live")
    gone = tmp_path / "vanished"
    registry.upsert("id-v", gone, "Vanished", gone / ".sillon", gone / ".sillon")

    result = projects_engine.prune_projects()
    assert result["removed_count"] == 1
    assert [r["project_name"] for r in projects_engine.get_projects(with_stats=False)] == ["Live"]
