"""The machine-wide project registry.

Regression guards for the three defects that made it unusable: entries were
appended once per init (206 rows for 32 paths), names were never recorded, and
the location was hardcoded to ~/.config regardless of platform.
"""

import sys
from pathlib import Path

import pytest
import toml

from silloncommon import registry
from silloncommon.user_paths import user_config_dir


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """Point the registry at a temp dir so tests never touch the real one."""
    monkeypatch.setattr(registry, "user_config_dir", lambda: tmp_path)
    return tmp_path / "registery.toml"


def _make_project(tmp_path, name):
    d = tmp_path / name
    (d / ".sillon").mkdir(parents=True)
    return d


# --- location ---------------------------------------------------------------


def test_config_dir_is_platform_appropriate(monkeypatch):
    """Windows must not get a stray ~/.config; POSIX must not move."""
    if sys.platform == "win32":
        monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
        assert user_config_dir() == Path(r"C:\Users\x\AppData\Roaming") / "sillon"
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg-probe")
        assert user_config_dir() == Path("/tmp/xdg-probe") / "sillon"


# --- upsert -----------------------------------------------------------------


def test_reinit_updates_in_place_instead_of_appending(isolated_registry, tmp_path):
    """The duplication bug: 206 rows for 32 paths."""
    project = _make_project(tmp_path, "proj")

    for _ in range(5):  # five inits of the same project, new uuid each time
        registry.upsert("id-%s" % _, project, "My Project", project / ".sillon", project / ".sillon")

    entries = registry.entries()
    assert len(entries) == 1
    assert entries[0]["project_name"] == "My Project"


def test_name_is_recorded(isolated_registry, tmp_path):
    project = _make_project(tmp_path, "named")
    registry.upsert("id1", project, "Shaking Lattice", project / ".sillon", project / ".sillon")
    assert registry.entries()[0]["project_name"] == "Shaking Lattice"


def test_existing_name_survives_a_nameless_reinit(isolated_registry, tmp_path):
    """A run started without project_name must not blank an existing name."""
    project = _make_project(tmp_path, "keepname")
    registry.upsert("id1", project, "Kept", project / ".sillon", project / ".sillon")
    registry.upsert("id2", project, "", project / ".sillon", project / ".sillon")
    assert registry.entries()[0]["project_name"] == "Kept"


def test_distinct_projects_get_distinct_entries(isolated_registry, tmp_path):
    a = _make_project(tmp_path, "a")
    b = _make_project(tmp_path, "b")
    registry.upsert("id1", a, "A", a / ".sillon", a / ".sillon")
    registry.upsert("id2", b, "B", b / ".sillon", b / ".sillon")
    assert len(registry.entries()) == 2


# --- exists / prune / repair ------------------------------------------------


def test_missing_projects_are_flagged_not_hidden(isolated_registry, tmp_path):
    gone = tmp_path / "deleted"
    registry.upsert("id1", gone, "Gone", gone / ".sillon", gone / ".sillon")
    entry = registry.entries()[0]
    assert entry["exists"] is False
    assert entry["project_name"] == "Gone"


def test_prune_removes_only_missing_projects(isolated_registry, tmp_path):
    alive = _make_project(tmp_path, "alive")
    gone = tmp_path / "gone"
    registry.upsert("id1", alive, "Alive", alive / ".sillon", alive / ".sillon")
    registry.upsert("id2", gone, "Gone", gone / ".sillon", gone / ".sillon")

    result = registry.prune()
    assert len(result) == 1
    remaining = registry.entries()
    assert len(remaining) == 1
    assert remaining[0]["project_name"] == "Alive"


def test_repair_collapses_legacy_duplicates(isolated_registry, tmp_path):
    """A registry written by an older sillon: one row per init, keyed by uuid."""
    project = _make_project(tmp_path, "legacy")
    legacy = {"project": {}}
    for i in range(20):
        legacy["project"][f"uuid-{i}"] = {
            "project_name": "Real Name" if i == 7 else "",
            "project_id": f"uuid-{i}",
            "project_path": str(project),
            "project_sil": str(project / ".sillon"),
            "project_storage": str(project / ".sillon"),
        }
    isolated_registry.parent.mkdir(parents=True, exist_ok=True)
    isolated_registry.write_text(toml.dumps(legacy), encoding="utf-8")

    summary = registry.repair()
    assert summary["before"] == 20
    assert summary["after"] == 1
    # The one row carrying a name must be the one that survives.
    assert registry.entries()[0]["project_name"] == "Real Name"


# --- resilience -------------------------------------------------------------


def test_missing_registry_reads_empty(isolated_registry):
    assert registry.entries() == []


def test_corrupt_registry_does_not_raise(isolated_registry):
    """A broken index must never take down the run trying to record itself."""
    isolated_registry.parent.mkdir(parents=True, exist_ok=True)
    isolated_registry.write_text("this is not [ valid toml", encoding="utf-8")
    assert registry.entries() == []
