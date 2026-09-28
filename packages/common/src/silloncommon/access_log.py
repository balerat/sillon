"""A record of which runs' data this process has read.

Provenance should be something sillon notices, not something you remember to
declare. The common pattern is:

    prev  = sl.load_project().get("equilibrated")
    state = prev.load_result("final_state")      # <- recorded here

    with sp.track_run():                          # <- drained here
        sp.log_result("trajectory", evolve(state))

sillonlab writes to this log whenever a run's *data* is actually loaded, and
sillonpy drains it when a run is sealed, turning each entry into a parent edge.
Neither library has to import the other: the log sits below both.

Deliberately narrow about what counts. Browsing a project — listing runs,
reading parameters, building a dataframe — records nothing, because looking at
a run is not deriving from it. Only pulling its stored data does.

Process-local, and that is a real limit: load data in a notebook, write it to a
file, then run a separate script and there is no link, because nothing observed
both halves. Stated in the docs rather than papered over.
"""

import threading

__all__ = ["record_read", "reads", "drain", "clear", "set_enabled", "is_enabled"]

_lock = threading.Lock()
_reads = {}  # run uuid -> {"uuid", "name", "items": set}
_enabled = True


def set_enabled(enabled: bool) -> None:
    """Turn recording on or off for this process."""
    global _enabled
    _enabled = bool(enabled)


def is_enabled() -> bool:
    return _enabled


def record_read(run_uuid, run_name, item: str = None) -> None:
    """Note that this process read a run's data.

    Args:
        run_uuid (str): The run that was read. Entries without one are ignored —
            a uuid is what makes the edge meaningful across a rename.
        run_name (str): Its name, kept for display.
        item (str, optional): Which result/parameter/analysis was read.
    """
    if not _enabled or not run_uuid:
        return
    with _lock:
        entry = _reads.setdefault(
            str(run_uuid), {"uuid": str(run_uuid), "name": run_name, "items": set()}
        )
        if run_name and not entry.get("name"):
            entry["name"] = run_name
        if item:
            entry["items"].add(str(item))


def reads() -> list:
    """What has been read so far, without clearing it."""
    with _lock:
        return [
            {"uuid": e["uuid"], "name": e["name"], "items": sorted(e["items"])}
            for e in _reads.values()
        ]


def drain(exclude_uuid=None) -> list:
    """Take everything recorded and reset the log.

    Args:
        exclude_uuid (str, optional): A run to leave out — normally the run
            being sealed, so that reading your own data is not self-lineage.

    Returns:
        list[dict]: `{"uuid", "name", "items"}` per run read.
    """
    entries = reads()
    clear()
    if exclude_uuid:
        entries = [e for e in entries if e["uuid"] != str(exclude_uuid)]
    return entries


def clear() -> None:
    """Forget every read so far.

    For a long exploratory session where earlier browsing should not attach
    itself to the next run you log.
    """
    with _lock:
        _reads.clear()
