"""`.sillon/config.toml` has one reader, and it must answer what the writer meant.

Before this module existed, three places parsed the file independently: the
daemon's project handler, its per-run handler, and `project_paths`. The daemon
honoured `[storage].storage_root`; the readers had the same lines commented out
and always assumed `.sillon`. Nothing caught it because the two answers
coincide in the default layout — which is every project anyone had.

So these tests are mostly about the cases where they *don't* coincide.
"""

from pathlib import Path

import toml

from silloncommon import project_config as pc


def _write(project, config):
    sillon = project / ".sillon"
    sillon.mkdir(parents=True, exist_ok=True)
    (sillon / "config.toml").write_text(toml.dumps(config))


# ==========================================
#              THE DEFAULT LAYOUT
# ==========================================
def test_no_config_at_all(tmp_path):
    """A project directory with nothing in it still has an answer."""
    assert pc.resolve_storage_root(tmp_path) == tmp_path / ".sillon"


def test_a_config_without_a_storage_section(tmp_path):
    _write(tmp_path, {"Environment": {"project_id": "x", "project_name": "P"}})
    assert pc.resolve_storage_root(tmp_path) == tmp_path / ".sillon"


def test_an_unreadable_config_does_not_raise(tmp_path):
    """A corrupt config must not stop a run from being logged."""
    sillon = tmp_path / ".sillon"
    sillon.mkdir(parents=True)
    (sillon / "config.toml").write_text("this is not = = toml [[[")
    assert pc.resolve_storage_root(tmp_path) == sillon
    assert pc.read_config(tmp_path) == {}
    assert pc.project_name(tmp_path) == ""


# ==========================================
#            RELATIVE, SO IT TRAVELS
# ==========================================
def test_a_relative_root_resolves_against_the_project(tmp_path):
    _write(tmp_path, {"storage": {"storage_root": ".sillon"}})
    assert pc.resolve_storage_root(tmp_path) == tmp_path / ".sillon"


def test_a_root_inside_the_project_is_stored_relative(tmp_path):
    """The whole point: a moved or copied project keeps a valid root."""
    assert pc.store_storage_root(tmp_path, tmp_path / ".sillon") == ".sillon"
    assert pc.store_storage_root(tmp_path, tmp_path / "data" / "big") == "data/big"


def test_a_root_outside_the_project_stays_absolute(tmp_path):
    """Heavy data on another disk cannot be expressed relatively."""
    external = tmp_path.parent / "elsewhere-on-another-disk"
    stored = pc.store_storage_root(tmp_path, external)
    assert Path(stored).is_absolute()
    assert Path(stored) == external.resolve()


def test_a_relative_root_survives_the_project_moving(tmp_path):
    """Write the config at one path, read it at another."""
    before = tmp_path / "before"
    (before / "data").mkdir(parents=True)
    _write(before, {"storage": {"storage_root": "data"}})

    after = tmp_path / "after"
    before.rename(after)

    assert pc.resolve_storage_root(after) == after / "data"


# ==========================================
#              EXTERNAL ROOTS
# ==========================================
def test_an_absolute_root_that_exists_is_honoured(tmp_path):
    external = tmp_path / "bigdisk" / "sillon-storage"
    external.mkdir(parents=True)
    _write(tmp_path, {"storage": {"storage_root": str(external)}})
    assert pc.resolve_storage_root(tmp_path) == external.resolve()


def test_an_absolute_root_that_is_gone_falls_back(tmp_path):
    """A project moved while its data lived on a disk that is not here.

    Answering with the recorded path would only produce confusing errors
    deeper in — a glob that cannot be opened, an artifact that is not there.
    `sillon check` is where this gets reported.
    """
    _write(tmp_path, {"storage": {"storage_root": "/nowhere/that/exists/at/all"}})
    assert pc.resolve_storage_root(tmp_path) == tmp_path / ".sillon"


# ==========================================
#                  IDENTITY
# ==========================================
def test_project_id_and_name_come_from_the_project(tmp_path):
    _write(
        tmp_path,
        {"Environment": {"project_id": "abc-123", "project_name": "Shaking Lattice"}},
    )
    assert pc.project_id(tmp_path) == "abc-123"
    assert pc.project_name(tmp_path) == "Shaking Lattice"


def test_an_empty_name_reads_as_empty_not_none(tmp_path):
    """Callers do `name or fallback`; None would work but "" is the contract."""
    _write(tmp_path, {"Environment": {"project_id": "abc", "project_name": ""}})
    assert pc.project_name(tmp_path) == ""
    assert pc.project_id(tmp_path) == "abc"


def test_write_then_read_round_trip(tmp_path):
    pc.write_config(tmp_path, {"Environment": {"project_name": "Round Trip"}})
    assert pc.project_name(tmp_path) == "Round Trip"
    assert pc.config_path(tmp_path).exists()


# ==========================================
#          THE READERS ALL AGREE NOW
# ==========================================
def test_silloncore_resolver_is_the_same_function(tmp_path):
    """`project_paths.resolve_storage_root` must not drift again."""
    from silloncore.project_paths import resolve_storage_root

    assert resolve_storage_root is pc.resolve_storage_root


def test_the_source_store_sits_in_the_storage_root(tmp_path):
    """Sources travel with the data an import copies, not beside the project."""
    from silloncommon.source_store import sources_dir

    # Default layout: unchanged from .sillon/sources.
    assert sources_dir(tmp_path / ".sillon") == tmp_path / ".sillon" / "sources"
    # Custom layout: with the rest of the run data.
    assert sources_dir(tmp_path / "bigdisk") == tmp_path / "bigdisk" / "sources"
