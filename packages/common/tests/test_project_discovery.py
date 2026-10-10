"""Finding the project you are in, and recognising one that has moved.

Two things that were missing, and that matter more now that projects travel:

- Both entry points demanded you stand in the project root. Running
  `sillon list` from `analysis/figures/` failed, which is the one place you
  are standing when you want to look something up.
- A project carries its identity in its own `config.toml`, so `mv`-ing one is
  a perfectly reasonable thing to do. It just left this machine's registry
  pointing at where the project used to be, which `sillon projects` then
  showed as a phantom.
"""

import toml

from silloncommon import project_config, registry


def _make(path, project_id="p-1", name="P"):
    sillon = path / ".sillon"
    sillon.mkdir(parents=True, exist_ok=True)
    (sillon / "config.toml").write_text(
        toml.dumps(
            {
                "Environment": {"project_id": project_id, "project_name": name},
                "storage": {"storage_root": ".sillon"},
            }
        )
    )
    return path


# ==========================================
#            SEARCHING UPWARD
# ==========================================
def test_the_root_itself(tmp_path):
    project = _make(tmp_path / "proj")
    assert project_config.find_project_root(project) == project.resolve()


def test_a_directory_deep_inside(tmp_path):
    project = _make(tmp_path / "proj")
    deep = project / "analysis" / "figures" / "paper"
    deep.mkdir(parents=True)
    assert project_config.find_project_root(deep) == project.resolve()


def test_a_file_inside(tmp_path):
    """A notebook's `__file__`, not its directory."""
    project = _make(tmp_path / "proj")
    notebook = project / "analysis" / "look.ipynb"
    notebook.parent.mkdir(parents=True)
    notebook.write_text("{}")
    assert project_config.find_project_root(notebook) == project.resolve()


def test_nothing_above(tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert project_config.find_project_root(outside) is None


def test_the_nearest_one_wins(tmp_path):
    """Sillon never nests projects, but a user can still produce this."""
    outer = _make(tmp_path / "outer", project_id="outer")
    inner = _make(outer / "inner", project_id="inner")
    assert project_config.find_project_root(inner / "sub") == inner.resolve()


def test_a_dot_sillon_file_rather_than_a_directory(tmp_path):
    """Something named `.sillon` that is not one must not count."""
    odd = tmp_path / "odd"
    odd.mkdir()
    (odd / ".sillon").write_text("not a directory")
    assert project_config.find_project_root(odd) is None


# ==========================================
#          A PROJECT THAT HAS MOVED
# ==========================================
def _registry_rows(monkeypatch, tmp_path):
    """Point the registry at a throwaway config directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return registry


def test_a_moved_project_is_re_registered(monkeypatch, tmp_path):
    reg = _registry_rows(monkeypatch, tmp_path)
    before = _make(tmp_path / "before", project_id="mover", name="Mover")
    reg.upsert("mover", before, "Mover", before / ".sillon", before / ".sillon")

    after = tmp_path / "after"
    before.rename(after)

    assert reg.register_if_moved(after) is True
    rows = [e for e in reg.entries() if e["project_id"] == "mover"]
    assert len(rows) == 1, "a phantom row was left behind"
    assert rows[0]["project_path"] == str(after.resolve())
    assert rows[0]["project_name"] == "Mover"


def test_a_project_that_has_not_moved_is_not_rewritten(monkeypatch, tmp_path):
    """The common case, on every single command. It must do nothing."""
    reg = _registry_rows(monkeypatch, tmp_path)
    project = _make(tmp_path / "still", project_id="still")
    reg.upsert("still", project, "Still", project / ".sillon", project / ".sillon")

    assert reg.register_if_moved(project) is False


def test_a_project_never_registered_here_is_not_invented(monkeypatch, tmp_path):
    """A project copied from another machine: registering it is `init`'s job."""
    reg = _registry_rows(monkeypatch, tmp_path)
    foreign = _make(tmp_path / "foreign", project_id="elsewhere")
    assert reg.register_if_moved(foreign) is False
    assert reg.entries() == []


def test_a_project_with_no_recorded_id(monkeypatch, tmp_path):
    """Pre-2.0: nothing to match on, so nothing to heal."""
    reg = _registry_rows(monkeypatch, tmp_path)
    old = tmp_path / "old"
    (old / ".sillon").mkdir(parents=True)
    (old / ".sillon" / "config.toml").write_text(toml.dumps({"storage": {}}))
    assert reg.register_if_moved(old) is False


def test_the_name_is_kept_when_the_project_has_none(monkeypatch, tmp_path):
    """The registry may be the only thing that remembers what it was called."""
    reg = _registry_rows(monkeypatch, tmp_path)
    before = _make(tmp_path / "before", project_id="m", name="")
    reg.upsert("m", before, "Remembered", before / ".sillon", before / ".sillon")

    after = tmp_path / "after"
    before.rename(after)
    reg.register_if_moved(after)

    rows = [e for e in reg.entries() if e["project_id"] == "m"]
    assert rows[0]["project_name"] == "Remembered"


def test_upsert_follows_the_id_when_the_path_is_new(monkeypatch, tmp_path):
    """The mechanism under the healing, exercised directly."""
    reg = _registry_rows(monkeypatch, tmp_path)
    reg.upsert("same-id", tmp_path / "one", "First", tmp_path / "one", tmp_path / "one")
    reg.upsert("same-id", tmp_path / "two", "First", tmp_path / "two", tmp_path / "two")

    rows = reg.entries()
    assert len(rows) == 1
    assert rows[0]["project_path"] == str((tmp_path / "two").resolve())


def test_two_different_projects_still_get_two_rows(monkeypatch, tmp_path):
    reg = _registry_rows(monkeypatch, tmp_path)
    reg.upsert("a", tmp_path / "a", "A", tmp_path / "a", tmp_path / "a")
    reg.upsert("b", tmp_path / "b", "B", tmp_path / "b", tmp_path / "b")
    assert len(reg.entries()) == 2
