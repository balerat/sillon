"""`sillon init`, and the one implementation of "make this a project".

A project has always come into existence as a side effect of the first run
being logged, and still does — zero-config logging is the whole point. What
that side effect cannot do is name a project before it has any runs, or put
its heavy data on a different disk, and until now there was nowhere to ask.

`create_project` is shared with the daemon, so a project `init` makes and a
project the first run makes are the same thing. These tests pin that, and the
idempotence that makes it safe for the daemon to call on every run.
"""

import pytest
import toml

from silloncommon import project_config, registry
from silloncore.project_paths import resolve_engine
from silloncore.projects import create_project

import silloncli.commands.init as init


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def _init(path=None, name=None, storage_root=None, cwd=None, monkeypatch=None):
    if cwd is not None:
        monkeypatch.chdir(cwd)
    return init.command(
        None, None, {"path": str(path) if path else None, "name": name,
                     "storage_root": str(storage_root) if storage_root else None},
    )


# ==========================================
#              CREATING ONE
# ==========================================
def test_init_makes_a_project(tmp_path):
    target = tmp_path / "fresh"
    target.mkdir()
    result = _init(target, name="Fresh")

    assert result["created"] is True
    assert result["project_name"] == "Fresh"
    assert (target / ".sillon" / "config.toml").is_file()
    assert (target / ".sillon" / "database.sql").is_file()
    assert project_config.project_id(target)


def test_the_database_is_usable_immediately(tmp_path):
    """An empty project must open, not fail for having no runs."""
    from silloncommon.database import SCHEMA_VERSION, schema_version, select_run_index

    target = tmp_path / "fresh"
    _init(target, name="Fresh")

    engine = resolve_engine(target)
    assert select_run_index(engine) == []
    assert schema_version(engine) == SCHEMA_VERSION


def test_init_registers_the_project(tmp_path):
    target = tmp_path / "fresh"
    _init(target, name="Registered")

    rows = [e for e in registry.entries() if e["project_name"] == "Registered"]
    assert len(rows) == 1
    assert rows[0]["project_path"] == str(target.resolve())


def test_init_without_a_name(tmp_path):
    """Allowed: the first run that passes `project_name` sets it."""
    target = tmp_path / "anon"
    result = _init(target)
    assert result["project_name"] == ""
    assert result["created"] is True


def test_init_defaults_to_the_current_directory(tmp_path, monkeypatch):
    target = tmp_path / "here"
    target.mkdir()
    result = _init(name="Here", cwd=target, monkeypatch=monkeypatch)
    assert result["path"] == target.resolve()


def test_init_creates_missing_parent_directories(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    result = _init(target, name="Deep")
    assert result["created"] is True
    assert (target / ".sillon").is_dir()


# ==========================================
#              A STORAGE ROOT
# ==========================================
def test_a_custom_storage_root_is_honoured_by_readers(tmp_path):
    """The plumbing existed on both ends and was dead on both until 2.1."""
    target = tmp_path / "split"
    external = tmp_path / "bigdisk" / "store"
    result = _init(target, name="Split", storage_root=external)

    assert result["storage_root"] == external.resolve()
    assert (external / "database.sql").is_file()
    assert not (target / ".sillon" / "database.sql").exists()
    # And the reader agrees with the writer, which is the part that was broken.
    assert project_config.resolve_storage_root(target) == external.resolve()
    resolve_engine(target)  # must not raise


def test_a_storage_root_inside_the_project_is_recorded_relative(tmp_path):
    target = tmp_path / "proj"
    _init(target, name="P", storage_root=target / "data")
    recorded = toml.loads(
        (target / ".sillon" / "config.toml").read_text()
    )["storage"]["storage_root"]
    assert recorded == "data"


# ==========================================
#               IDEMPOTENCE
# ==========================================
def test_init_on_an_existing_project_changes_nothing(tmp_path):
    target = tmp_path / "proj"
    first = _init(target, name="Original")
    second = _init(target, name="Renamed")

    assert second["created"] is False
    assert second["project_name"] == "Original", "init renamed an existing project"
    assert second["project_id"] == first["project_id"]


def test_an_existing_project_keeps_its_storage_root(tmp_path):
    """Moving data is not something `init` should do behind your back."""
    target = tmp_path / "proj"
    _init(target, name="P")
    result = _init(target, storage_root=tmp_path / "somewhere-else")
    assert result["storage_root"] == (target / ".sillon").resolve()


def test_init_inside_an_existing_project_is_refused(tmp_path, monkeypatch):
    """Sillon never nests projects, so the useful answer is which one you are in."""
    outer = tmp_path / "outer"
    _init(outer, name="Outer")
    inner = outer / "analysis"
    inner.mkdir()

    assert _init(inner, name="Inner") is None
    assert not (inner / ".sillon").exists()


def test_exist_ok_false_raises(tmp_path):
    target = tmp_path / "proj"
    create_project(target, project_name="P")
    with pytest.raises(FileExistsError, match="already a sillon project"):
        create_project(target, exist_ok=False)


def test_a_bare_sillon_directory_counts_as_new(tmp_path):
    """A `.sillon/` with no config is not a project yet — finish the job."""
    target = tmp_path / "half"
    (target / ".sillon").mkdir(parents=True)
    result = create_project(target, project_name="Half")
    assert result["created"] is True
    assert result["project_name"] == "Half"
