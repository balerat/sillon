"""Comparing runs: what changed, and did it matter.

Two shapes of question, both answered here:

* **Pairwise** — *"these two runs disagree; why?"* Parameters with a real
  delta, whether the code differed and how, and whether the results actually
  moved.
* **N-way** — *"what was this sweep varying?"* The axis of variation across a
  set of runs, which is the question you have six months later when the sweep
  is a folder of names you no longer recognise.

Data is compared by **shape, dtype and hash**, never element-wise. Shape and
dtype come from the HDF5 header for free, so two arrays of different shape are
known to differ without either being read. Only arrays below a size threshold
are loaded to hash; bigger ones report what is known and say plainly that they
were not compared, rather than stalling a diff on a gigabyte.
"""

import math
from difflib import unified_diff
from pathlib import Path

from silloncommon.source_store import read_source

from silloncore.glob import glob_descriptors, read_glob

# Arrays at or below this are loaded to hash and summarise; above it only the
# header is used. 64 MB keeps a diff interactive on ordinary results while
# still covering most of what people actually compare.
DEFAULT_MAX_COMPARE_BYTES = 64 * 1024 * 1024

__all__ = ["diff_runs", "diff_across", "percent_delta", "DEFAULT_MAX_COMPARE_BYTES"]


# ==========================================
#                 VALUES
# ==========================================


def percent_delta(old, new):
    """Relative change between two numbers, or None when that is meaningless.

    Returns None for non-numeric values, for booleans (where a percentage says
    nothing), and when the baseline is zero — a change from 0 has no defined
    relative size, and reporting `inf` would be worse than reporting nothing.
    """
    if isinstance(old, bool) or isinstance(new, bool):
        return None
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
        return None
    if old == 0 or not math.isfinite(old) or not math.isfinite(new):
        return None
    return (new - old) / abs(old) * 100.0


def _summarise_inline(value) -> dict:
    """Describe a value held in the database (small, already in memory)."""
    if isinstance(value, (list, tuple)):
        return {"kind": "sequence", "length": len(value)}
    if isinstance(value, dict):
        # A staged-array marker records its own shape and dtype.
        if value.get("__sillon_array_ref__"):
            return {
                "kind": "array",
                "shape": tuple(value.get("shape") or ()),
                "dtype": value.get("dtype"),
                "hash": value.get("hash"),
            }
        return {"kind": "mapping", "length": len(value)}
    return {"kind": "scalar", "value": value}


def _hash_and_stats(storage_root, uuid, group, name):
    """Load one dataset to hash it and take summary statistics."""
    from silloncommon.hashing import get_hash

    data = read_glob(storage_root, uuid, group, name)
    if data is None:
        return {}

    summary = {"hash": get_hash(data)}
    try:
        import numpy as np

        array = np.asarray(data)
        if array.size and np.issubdtype(array.dtype, np.number):
            summary["stats"] = {
                "min": float(np.min(array)),
                "max": float(np.max(array)),
                "mean": float(np.mean(array)),
            }
    except Exception:
        pass
    return summary


def _summarise_stored(storage_root, snapshot, name, descriptors, max_bytes):
    """Describe one stored result: header first, contents only if small enough."""
    descriptor = descriptors.get(name)
    if descriptor is None:
        # Not in the glob: an inline database value or an artifact path.
        return _summarise_inline(snapshot["results"].get(name))

    # A logged scalar lands in the glob as a 0-d dataset. Treated as an array it
    # would compare by hash and report "contents differ" — true but useless,
    # when what you want is 4.774 -> 4.767 (-0.15%). So read it back as a value.
    shape = descriptor["shape"]
    if not shape or math.prod(shape) == 1:
        value = read_glob(storage_root, snapshot["uuid"], "result", name)
        try:
            import numpy as np

            array = np.asarray(value)
            if array.size == 1:
                return {"kind": "scalar", "value": array.reshape(-1)[0].item()}
        except Exception:
            pass
        return {"kind": "scalar", "value": value}

    summary = {
        "kind": "array",
        "shape": shape,
        "dtype": descriptor["dtype"],
        "nbytes": descriptor["nbytes"],
    }
    if descriptor["nbytes"] <= max_bytes:
        summary.update(_hash_and_stats(storage_root, snapshot["uuid"], "result", name))
    else:
        summary["compared"] = False
    return summary


def _compare_summaries(old, new):
    """Decide whether two described values differ, and how confidently.

    Shape or dtype differences are conclusive on their own. Hashes settle the
    rest. When neither side was loaded, say so instead of guessing.
    """
    if old.get("kind") == "scalar" and new.get("kind") == "scalar":
        same = old.get("value") == new.get("value")
        return {
            "changed": not same,
            "reason": None if same else "value",
            "delta_pct": percent_delta(old.get("value"), new.get("value")),
        }

    if old.get("shape") != new.get("shape"):
        return {"changed": True, "reason": "shape", "delta_pct": None}
    if old.get("dtype") != new.get("dtype"):
        return {"changed": True, "reason": "dtype", "delta_pct": None}

    old_hash, new_hash = old.get("hash"), new.get("hash")
    if old_hash and new_hash:
        return {
            "changed": old_hash != new_hash,
            "reason": "contents" if old_hash != new_hash else None,
            "delta_pct": None,
        }

    if old.get("compared") is False or new.get("compared") is False:
        return {"changed": None, "reason": "too_large", "delta_pct": None}

    return {"changed": old != new, "reason": "value", "delta_pct": None}


# ==========================================
#                  CODE
# ==========================================


def _code_files(snapshot) -> dict:
    version = (snapshot.get("meta_data") or {}).get("sillon.code.version") or {}
    return version.get("files") or {}


def _diff_code(storage_root, snap_a, snap_b) -> dict:
    """Compare the code behind two runs, using the recorded version hashes.

    The useful distinction, and the reason code versions exist: *same logic,
    only a constant differs* is a comparable pair; a changed expression is not.
    """
    files_a, files_b = _code_files(snap_a), _code_files(snap_b)
    version_a = snap_a.get("logic_version")
    version_b = snap_b.get("logic_version")

    result = {
        "logic_version": (version_a, version_b),
        "same_logic": bool(version_a) and version_a == version_b,
        "known": bool(files_a or files_b or version_a or version_b),
        "files": {},
        "constants_differ": False,
        "source_diff": "",
    }

    diffs = []
    for name in sorted(set(files_a) | set(files_b)):
        a, b = files_a.get(name), files_b.get(name)
        if a is None:
            result["files"][name] = {"status": "added"}
            continue
        if b is None:
            result["files"][name] = {"status": "removed"}
            continue

        if a["logic_hash"] != b["logic_hash"]:
            status = "changed"
        elif a["ast_hash"] != b["ast_hash"]:
            status = "constants"          # same program, different literals
            result["constants_differ"] = True
        elif a["source_hash"] != b["source_hash"]:
            status = "cosmetic"           # comments or formatting only
        else:
            status = "same"
        result["files"][name] = {"status": status}

        if status in ("changed", "constants"):
            text_a = read_source(storage_root_project(storage_root), a["source_hash"])
            text_b = read_source(storage_root_project(storage_root), b["source_hash"])
            if text_a is not None and text_b is not None:
                diffs.extend(
                    unified_diff(
                        text_a.splitlines(keepends=True),
                        text_b.splitlines(keepends=True),
                        fromfile=f"{name} @ {snap_a['name']}",
                        tofile=f"{name} @ {snap_b['name']}",
                    )
                )

    result["source_diff"] = "".join(diffs)
    return result


def storage_root_project(storage_root) -> Path:
    """The project root that owns a storage root.

    The source store lives beside the database at `.sillon/sources`, while
    callers hand around the storage root — which *is* `.sillon` in the default
    layout. Normalised here so both spellings resolve.
    """
    path = Path(storage_root)
    return path.parent if path.name == ".sillon" else path


# ==========================================
#                PAIRWISE
# ==========================================


def diff_runs(engine, storage_root, snapshot_a, snapshot_b, max_bytes=None) -> dict:
    """Compare two runs: parameters, code, results and execution context.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        storage_root (str | Path): The project storage root.
        snapshot_a (dict): Baseline run snapshot from `get_run_snapshot`.
        snapshot_b (dict): Target run snapshot.
        max_bytes (int, optional): Largest array to load for hashing. Bigger
            results are reported by shape and dtype and flagged as not compared.

    Returns:
        dict: `{"runs", "parameters", "code", "results", "context"}`.
    """
    max_bytes = DEFAULT_MAX_COMPARE_BYTES if max_bytes is None else max_bytes

    # --- parameters -------------------------------------------------------
    params_a = snapshot_a.get("parameters") or {}
    params_b = snapshot_b.get("parameters") or {}
    changed, unchanged = {}, 0
    for key in sorted(set(params_a) & set(params_b)):
        old, new = params_a[key], params_b[key]
        if old == new:
            unchanged += 1
            continue
        changed[key] = {"old": old, "new": new, "delta_pct": percent_delta(old, new)}

    parameters = {
        "changed": changed,
        "added": sorted(set(params_b) - set(params_a)),
        "removed": sorted(set(params_a) - set(params_b)),
        "unchanged": unchanged,
    }

    # --- results ----------------------------------------------------------
    desc_a = glob_descriptors(storage_root, snapshot_a["uuid"], "result")
    desc_b = glob_descriptors(storage_root, snapshot_b["uuid"], "result")
    names_a = set(snapshot_a.get("results") or {})
    names_b = set(snapshot_b.get("results") or {})

    results = {}
    for name in sorted(names_a | names_b):
        if name not in names_a:
            results[name] = {"status": "added"}
            continue
        if name not in names_b:
            results[name] = {"status": "removed"}
            continue

        old = _summarise_stored(storage_root, snapshot_a, name, desc_a, max_bytes)
        new = _summarise_stored(storage_root, snapshot_b, name, desc_b, max_bytes)
        verdict = _compare_summaries(old, new)
        results[name] = {
            "status": {True: "changed", False: "same", None: "unknown"}[verdict["changed"]],
            "reason": verdict["reason"],
            "delta_pct": verdict["delta_pct"],
            "old": old,
            "new": new,
        }

    # --- context ----------------------------------------------------------
    def _pair(key):
        a, b = snapshot_a.get(key), snapshot_b.get(key)
        return (a, b) if a != b else None

    return {
        "runs": [
            {
                "name": snap["name"],
                "uuid": snap["uuid"],
                "date": snap.get("date"),
                "status": snap.get("status"),
            }
            for snap in (snapshot_a, snapshot_b)
        ],
        "parameters": parameters,
        "code": _diff_code(storage_root, snapshot_a, snapshot_b),
        "results": results,
        "context": {"status": _pair("status"), "runtime": _pair("runtime")},
    }


# ==========================================
#                  N-WAY
# ==========================================


def diff_across(entries: list) -> dict:
    """What varies, and what is held fixed, across a set of runs.

    The question a sweep leaves behind: which knobs were actually turned?

    Args:
        entries (list[dict]): Run index entries (from `select_run_index`), or
            anything with `name`, `parameters` and `logic_version`.

    Returns:
        dict: `{"run_count", "varying", "constant", "logic_versions"}`, where
            `varying` maps a parameter to its distinct values and `constant`
            maps a parameter to the single value every run shared.
    """
    if not entries:
        return {"run_count": 0, "varying": {}, "constant": {}, "logic_versions": []}

    keys = set()
    for entry in entries:
        keys |= set(entry.get("parameters") or {})

    varying, constant = {}, {}
    for key in sorted(keys):
        values, hashable = [], True
        for entry in entries:
            value = (entry.get("parameters") or {}).get(key)
            try:
                hash(value)
            except TypeError:
                hashable = False
            values.append(value)

        present_in_all = all(key in (e.get("parameters") or {}) for e in entries)
        distinct = list(dict.fromkeys(values)) if hashable else values

        if present_in_all and hashable and len(distinct) == 1:
            constant[key] = distinct[0]
        else:
            varying[key] = distinct if hashable else ["<unhashable>"]

    versions = list(dict.fromkeys(e.get("logic_version") for e in entries))

    return {
        "run_count": len(entries),
        "varying": varying,
        "constant": constant,
        "logic_versions": [v for v in versions if v],
    }


# ==========================================
#               RESEMBLANCE
# ==========================================


def similarity(params_a: dict, params_b: dict) -> dict:
    """How alike two parameter sets are.

    Scored over the union of their keys, so a run that simply logged fewer
    parameters is not flattered by the ones it left out.

    Returns:
        dict: `{"score": 0..1, "shared": int, "differing": [keys],
            "only_in_a": [keys], "only_in_b": [keys]}`.
    """
    keys_a, keys_b = set(params_a), set(params_b)
    union = keys_a | keys_b
    if not union:
        return {
            "score": 1.0, "shared": 0, "differing": [],
            "only_in_a": [], "only_in_b": [], "distance": 0.0,
        }

    shared = [k for k in keys_a & keys_b if params_a[k] == params_b[k]]
    differing = sorted(k for k in keys_a & keys_b if params_a[k] != params_b[k])

    # Structural overlap alone cannot tell `ridge 0.0 -> 0.1` from
    # `degree 3 -> 1`: both are one key out of four. So numeric differences
    # also get a magnitude, used only to order runs that tie on overlap.
    gaps = []
    for key in differing:
        delta = percent_delta(params_a[key], params_b[key])
        gaps.append(min(abs(delta) / 100.0, 1.0) if delta is not None else 1.0)

    return {
        "score": len(shared) / len(union),
        "shared": len(shared),
        "differing": differing,
        "only_in_a": sorted(keys_a - keys_b),
        "only_in_b": sorted(keys_b - keys_a),
        "distance": sum(gaps) / len(gaps) if gaps else 0.0,
    }


def rank_similar(target: dict, entries: list, limit: int = 10) -> list:
    """Runs most like a given one, by how much of its configuration they share.

    Answers "did I do something close to this?" — the useful version of
    duplicate detection, since an exact-match check only fires on a perfect
    repeat and says nothing about the near misses.

    Args:
        target (dict): The run index entry to compare against.
        entries (list[dict]): Candidate entries.
        limit (int): How many to return.

    Returns:
        list[dict]: Newest-scoring first, each `{"name", "uuid", "score",
            "differing", "changes", "same_code"}`, where `changes` maps a
            differing parameter to its `(target value, candidate value)`.
    """
    target_params = target.get("parameters") or {}
    ranked = []

    for entry in entries:
        if entry["uuid"] == target["uuid"]:
            continue
        params = entry.get("parameters") or {}
        verdict = similarity(target_params, params)
        ranked.append(
            {
                "name": entry["name"],
                "uuid": entry["uuid"],
                "score": verdict["score"],
                "distance": verdict["distance"],
                "differing": verdict["differing"],
                "changes": {
                    key: (target_params.get(key), params.get(key))
                    for key in verdict["differing"]
                },
                "only_in_other": verdict["only_in_b"],
                "missing_here": verdict["only_in_a"],
                "same_code": bool(target.get("logic_version"))
                and target.get("logic_version") == entry.get("logic_version"),
            }
        )

    # Overlap first; among ties, whichever changed least.
    ranked.sort(key=lambda r: (-r["score"], r["distance"], r["name"]))
    return ranked[:limit]
