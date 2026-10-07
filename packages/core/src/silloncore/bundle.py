"""The sillon bundle: a project's runs as one portable file.

`report` already produces a zip, but it is a *report* — a manifest and a
markdown summary for a colleague to read, lossy by design. Results over 512
bytes become a size with no data, and artifact bytes and figure images are
never in it at all, even with `--with-data`. Nothing has ever read one back.

A bundle is the other thing: everything needed to reconstruct a run somewhere
else, and nothing else. Its layout deliberately mirrors the on-disk layout, so
importing is a directory copy rather than dataset surgery:

    sillon-bundle.json              what this is and where it came from
    runs/<run-uuid>/
      run.json                      the run row and its child rows
      glob/glob.hdf5                copied verbatim
      artifact/<artifact-uuid>/...  copied verbatim
      figure/<figure-uuid>/...      copied verbatim
    sources/<sha256>                the code behind the included runs

That works because `ArtifactTable.path` and `FigureTable.path` hold a **uuid
folder name**, not a filesystem path — they are resolved at read time against
`<storage_root>/artifact/<run-uuid>/`. So a whole `<run-uuid>/` tree moves
with every pointer inside it still valid. The inner folders are never merged.

Zip rather than tar because it is in the standard library, has an index (so
reading one run out of a large bundle does not stream the whole thing), and is
what `report` already uses. ZIP64 is automatic, so a bundle is not capped at
4 GB.
"""

import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from silloncommon import project_config, timestamps
from silloncommon.database import SCHEMA_VERSION, schema_version, select_run_snapshot
from silloncommon import __version__ as SILLON_VERSION

__all__ = [
    "BUNDLE_FORMAT",
    "BUNDLE_SUFFIX",
    "MANIFEST_NAME",
    "BundleError",
    "write_bundle",
    "read_manifest",
    "BundleSource",
    "default_bundle_name",
]

# Bumped only when a reader would get something wrong. A reader refuses a
# format from the future rather than importing part of it.
BUNDLE_FORMAT = 1

MANIFEST_NAME = "sillon-bundle.json"
BUNDLE_SUFFIX = ".sillon"

# The groups of heavy data a run owns, each a directory named by the run uuid.
DATA_GROUPS = ("glob", "artifact", "figure")


class BundleError(Exception):
    """A bundle that cannot be read, or cannot be trusted to be read."""


def _safe(text: str) -> str:
    """A filename fragment: no separators, no surprises on any platform."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(text or "")).strip("-")
    return cleaned or "sillon"


def default_bundle_name(project_path, hostname: str) -> str:
    """`<project>~<host>~<when>.sillon` — self-describing in a shared folder.

    The point is that a drive holding bundles from three machines can be read
    at a glance, and that two machines exporting at the same moment do not
    collide. The stamp is compact UTC: an offset in a filename either collides
    with the separator or reads as part of the time.
    """
    name = project_config.project_name(project_path) or Path(project_path).name
    stamp = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    return f"{_safe(name)}~{_safe(hostname)}~{stamp}{BUNDLE_SUFFIX}"


# ==========================================
#                  WRITING
# ==========================================


def _run_record(engine, run_identifier: str) -> dict:
    """One run as plain data: its row plus its artifact, figure and analysis rows."""
    run, artifacts, figures, analyses = select_run_snapshot(engine, run_identifier)
    if run is None:
        raise BundleError(f"Run '{run_identifier}' is not in this project.")
    return {
        "run": run,
        "artifacts": artifacts,
        "figures": figures,
        "analyses": analyses,
    }


def _referenced_source_hashes(record: dict) -> set:
    """Every source blob the run's recorded code version points at."""
    meta = (record["run"].get("meta_data") or {})
    version = meta.get("sillon.code.version") or {}
    hashes = set()
    for entry in (version.get("files") or {}).values():
        digest = (entry or {}).get("source_hash")
        if digest:
            hashes.add(digest)
    # Runs logged before code versioning recorded only the entry script, whose
    # text lives in the glob rather than the source store.
    return hashes


def write_bundle(
    engine,
    storage_root,
    project_path,
    run_identifiers,
    dest=None,
    with_data: bool = True,
) -> dict:
    """Writes the given runs to a bundle file.

    Args:
        engine (Engine): The project's database engine.
        storage_root (str | Path): Where the project's data lives.
        project_path (str | Path): The project root.
        run_identifiers (list[str]): Run names or uuids to include.
        dest (str | Path, optional): A target file, or a directory to write a
            self-describing name into. Defaults to the current directory.
        with_data (bool): Include the heavy data. False writes an index-only
            bundle, whose runs import as stubs.

    Raises:
        BundleError: If no runs were given, or one does not exist.

    Returns:
        dict: `{"path", "runs", "bytes", "with_data", "skipped_data"}`.
    """
    storage_root = Path(storage_root)
    project_path = Path(project_path)

    if not run_identifiers:
        raise BundleError("Nothing to export: no runs matched.")

    records = [_run_record(engine, identifier) for identifier in run_identifiers]
    # Deduplicate: a caller may pass a name and a uuid for the same run.
    by_uuid = {record["run"]["uuid"]: record for record in records}

    hostname = next(
        (r["run"].get("hostname") for r in by_uuid.values() if r["run"].get("hostname")),
        "unknown",
    )
    target = _resolve_dest(dest, project_path, hostname)

    manifest = {
        "bundle_format": BUNDLE_FORMAT,
        "sillon_version": SILLON_VERSION,
        "schema_version": schema_version(engine) or SCHEMA_VERSION,
        "created": timestamps.now_pair()[1],
        "with_data": bool(with_data),
        "source": {
            "project_id": project_config.project_id(project_path),
            "project_name": project_config.project_name(project_path)
            or project_path.name,
            "hostname": hostname,
        },
        "runs": [
            {"uuid": uuid, "name": record["run"].get("name")}
            for uuid, record in by_uuid.items()
        ],
    }

    skipped_data = []
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, default=str))

        for uuid, record in by_uuid.items():
            archive.writestr(
                f"runs/{uuid}/run.json", json.dumps(record, indent=2, default=str)
            )
            if with_data:
                missing = _add_run_data(archive, storage_root, uuid)
                skipped_data.extend(missing)

        if with_data:
            for digest in sorted(
                set().union(*(_referenced_source_hashes(r) for r in by_uuid.values()))
                if by_uuid
                else set()
            ):
                blob = storage_root / "sources" / digest
                if blob.is_file():
                    archive.write(blob, f"sources/{digest}")

    return {
        "path": target,
        "runs": [record["run"].get("name") for record in by_uuid.values()],
        "bytes": target.stat().st_size,
        "with_data": bool(with_data),
        # Data a row claims to have that is not on disk -- a pruned run, or one
        # whose files were removed by hand. Reported rather than silently
        # producing a bundle that looks complete.
        "skipped_data": skipped_data,
    }


def _resolve_dest(dest, project_path, hostname: str) -> Path:
    """Where to write, accepting either a file or a directory."""
    if dest is None:
        return Path.cwd() / default_bundle_name(project_path, hostname)
    dest = Path(dest).expanduser()
    looks_like_dir = dest.is_dir() or str(dest).endswith(("/", "\\"))
    if looks_like_dir:
        return dest / default_bundle_name(project_path, hostname)
    return dest


def _add_run_data(archive, storage_root: Path, uuid: str) -> list:
    """Copy a run's `glob/`, `artifact/` and `figure/` trees in verbatim."""
    missing = []
    for group in DATA_GROUPS:
        folder = storage_root / group / str(uuid)
        if not folder.is_dir():
            if group == "glob":
                missing.append({"uuid": uuid, "group": group})
            continue
        for item in sorted(folder.rglob("*")):
            if item.is_file():
                archive.write(item, f"runs/{uuid}/{group}/{item.relative_to(folder)}")
    return missing


# ==========================================
#                  READING
# ==========================================


def read_manifest(path) -> dict:
    """The manifest of a bundle, without extracting anything else.

    Raises:
        BundleError: If the file is not a bundle, or is a format this sillon
            does not know how to read.
    """
    path = Path(path).expanduser()
    if not path.is_file():
        raise BundleError(f"No such bundle: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(MANIFEST_NAME)
    except zipfile.BadZipFile as exc:
        raise BundleError(f"{path.name} is not a sillon bundle ({exc}).") from exc
    except KeyError as exc:
        raise BundleError(
            f"{path.name} is a zip but not a sillon bundle: no {MANIFEST_NAME}. "
            "A `sillon report` archive is a different thing and cannot be imported."
        ) from exc

    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BundleError(f"{path.name} has an unreadable manifest ({exc}).") from exc

    found = manifest.get("bundle_format")
    if found != BUNDLE_FORMAT:
        if isinstance(found, int) and found > BUNDLE_FORMAT:
            raise BundleError(
                f"{path.name} was written by a newer sillon "
                f"(bundle format {found}, this one reads {BUNDLE_FORMAT}). "
                "Upgrade sillon to import it."
            )
        raise BundleError(
            f"{path.name} has an unrecognised bundle format ({found!r})."
        )
    return manifest


class BundleSource:
    """A bundle file, as a source an import can read runs out of.

    The reader half of the format. `transfer` drives this; keeping the two
    apart means a project directory can be the source instead, with no change
    to the importer.
    """

    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.manifest = read_manifest(self.path)
        self._archive = None

    # -- context management: a bundle is a file handle ---------------------
    def __enter__(self):
        self._archive = zipfile.ZipFile(self.path)
        return self

    def __exit__(self, *exc):
        if self._archive is not None:
            self._archive.close()
            self._archive = None
        return False

    @property
    def _zip(self):
        if self._archive is None:
            raise BundleError("BundleSource must be used as a context manager.")
        return self._archive

    # -- what is in here ---------------------------------------------------
    def describe(self) -> dict:
        source = self.manifest.get("source") or {}
        return {
            "kind": "bundle",
            "label": self.path.name,
            "project_id": source.get("project_id") or "",
            "project_name": source.get("project_name") or "",
            "hostname": source.get("hostname") or "",
            "created": self.manifest.get("created"),
            "sillon_version": self.manifest.get("sillon_version"),
            "schema_version": self.manifest.get("schema_version"),
            "has_data": bool(self.manifest.get("with_data")),
            "run_count": len(self.manifest.get("runs") or []),
        }

    def run_uuids(self) -> list:
        return [entry["uuid"] for entry in (self.manifest.get("runs") or [])]

    def read_run(self, uuid: str) -> dict:
        try:
            raw = self._zip.read(f"runs/{uuid}/run.json")
        except KeyError as exc:
            raise BundleError(f"{self.path.name} is missing run {uuid}.") from exc
        return json.loads(raw)

    def copy_run_data(self, uuid: str, storage_root) -> int:
        """Extract a run's data trees into a project's storage root.

        Returns:
            int: How many files were written.
        """
        storage_root = Path(storage_root)
        prefix = f"runs/{uuid}/"
        written = 0
        for info in self._zip.infolist():
            if info.is_dir() or not info.filename.startswith(prefix):
                continue
            relative = info.filename[len(prefix):]
            group = relative.split("/", 1)[0]
            if group not in DATA_GROUPS:
                continue  # run.json, or anything a later format adds
            target = storage_root / group / str(uuid) / Path(relative).relative_to(group)
            target.parent.mkdir(parents=True, exist_ok=True)
            with self._zip.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            written += 1
        return written

    def copy_sources(self, storage_root) -> int:
        """Add the bundle's source blobs to a project's store.

        The store is content-addressed, so this is a union: a blob already
        present cannot differ, because its name is the hash of its contents.

        Returns:
            int: How many blobs were newly written.
        """
        storage_root = Path(storage_root)
        written = 0
        for info in self._zip.infolist():
            if info.is_dir() or not info.filename.startswith("sources/"):
                continue
            digest = info.filename[len("sources/"):]
            if not digest or "/" in digest:
                continue
            target = storage_root / "sources" / digest
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            # Temp name then rename, so a concurrent reader never sees a
            # half-written blob -- same discipline as the client's writer.
            tmp = target.with_name(f".{digest}.import.tmp")
            with self._zip.open(info) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            tmp.replace(target)
            written += 1
        return written
