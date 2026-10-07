"""A content-addressed store for the source files behind each run.

Every run records the code that produced it, and across a sweep that code is
almost always identical — 135 runs of the same script would mean 135 copies of
the same text. Keying each file by the hash of its contents stores it once and
makes "was this the same file?" a name comparison.

Written by the client (like the staging directory) rather than shipped through
the daemon: the text is already on the client's disk, and a content-addressed
write is safe to race — two processes writing the same content write the same
bytes to the same name.
"""

import os
from pathlib import Path

__all__ = ["sources_dir", "store_source", "store_sources", "read_source", "has_source"]


def sources_dir(storage_root) -> Path:
    """Where a project's source blobs live, given its storage root.

    Keyed off the storage root rather than the project root so the text sits
    with the rest of a run's data -- `glob/`, `artifact/`, `figure/` -- which
    is what gets copied by an import and what a bundle carries. In the default
    layout the storage root *is* `.sillon`, so this is the same
    `.sillon/sources` as before.
    """
    return Path(storage_root) / "sources"


def _path_for(storage_root, digest: str) -> Path:
    return sources_dir(storage_root) / digest


def has_source(storage_root, digest: str) -> bool:
    return _path_for(storage_root, digest).exists()


def store_source(storage_root, digest: str, text: str) -> bool:
    """Write one source under its hash. Returns True if it was newly written.

    Skips the write when the digest is already present — the content cannot
    have changed, since the name *is* the content's hash.
    """
    target = _path_for(storage_root, digest)
    if target.exists():
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp name and rename, so a reader never sees a half-written
    # file if two runs store the same source at once.
    tmp = target.with_name(f".{digest}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)
        return False
    return True


def store_sources(storage_root, sources: dict, file_hashes: dict) -> int:
    """Store every source of a run. Returns how many were new.

    Args:
        storage_root: The project's storage root.
        sources (dict): `{name: source text}`.
        file_hashes (dict): `{name: {"source_hash": ..., ...}}` from
            `codeversion.compute_version`.
    """
    written = 0
    for name, text in sources.items():
        digest = (file_hashes.get(name) or {}).get("source_hash")
        if digest and store_source(storage_root, digest, text):
            written += 1
    return written


def read_source(storage_root, digest: str):
    """The stored text for a hash, or None if it is not in this project."""
    try:
        return _path_for(storage_root, digest).read_text(encoding="utf-8")
    except OSError:
        return None
