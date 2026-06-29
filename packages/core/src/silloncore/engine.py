import shutil
from pathlib import Path

from silloncommon.database import (
    select_param_user,
    select_metadata_user,
    select_result_user,
    select_all_user,
    select_key_user,
    select_run_snapshot,
    select_run_index,
    select_run_identities,
    select_by_hash,
    db_append_note_tag,
    db_append_metadata,
    db_insert_analysis,
    db_delete_runs,
    db_rename_run,
    next_available_name,
)

from silloncore.glob import read_glob, read_glob_many, append_glob, glob_sizes, get_hash
from silloncore.versioncontrol import Reference, Diffref


def get_project_context(engine, run_names: list = None) -> dict:
    """Fetches the context summary for the project or specific runs.

    This function operates in two modes: "overview" (if no run names are provided) 
    and "specific" (if targeted run names are provided). It returns pure data 
    dictionaries intended for downstream processing, containing absolutely no UI elements.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        run_names (list[str], optional): A list of specific run names or UUIDs to query. 
            Defaults to None, which triggers the project-wide overview mode.

    Returns:
        dict: A dictionary containing the query mode and the formatted run data.
            Format:
            ```python
            {
                "mode": "overview" | "specific",
                "runs": [
                    {
                        "id": str,
                        "name": str,
                        "timestamp": str,
                        "param_count": int,
                        "asset_count": int,
                        "status": str,
                        # ... additional keys in specific mode (runtime, language)
                    },
                    ...
                ]
            }
            ```
    """
    index = select_run_index(engine)
    index.sort(key=lambda entry: entry["date"] or "")  # by timestamp

    def _to_card(entry: dict) -> dict:
        assets = (
            len(entry["result_names"])
            + len(entry["artifacts"])
            + len(entry["figures"])
            + len(entry["analyses"])
        )
        return {
            "id": entry["uuid"],  # kept for backward-compat (now the uuid)
            "uuid": entry["uuid"],
            "name": entry["name"],
            "timestamp": entry["date"],
            "param_count": len(entry["parameters"]),
            "asset_count": assets,
            "status": entry["status"] or "N/A",
            "runtime": entry["runtime"] or "N/A",
            "language": (entry["meta_data"] or {}).get("sillon.language", "N/A"),
        }

    if not run_names:
        return {"mode": "overview", "runs": [_to_card(e) for e in index]}

    wanted = set(run_names)
    runs_data = [
        _to_card(e) for e in index if e["name"] in wanted or e["uuid"] in wanted
    ]
    return {"mode": "specific", "runs": runs_data}


def get_run_details(
    engine,
    run_names: list = None,
    params: list = None,
    meta: list = None,
    results: list = None,
) -> dict:
    """Universal API to fetch deep details for specific runs.

    This function extracts parameters, metadata, and results for given runs. 
    It understands the `"%all%"` wildcard string inside the specific query lists 
    to return all items of that category.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        run_names (list[str], optional): A list of run names or UUIDs to target. 
            Defaults to None.
        params (list[str], optional): A list of parameter keys to fetch, or `["%all%"]`. 
            Defaults to None.
        meta (list[str], optional): A list of metadata keys to fetch, or `["%all%"]`. 
            Defaults to None.
        results (list[str], optional): A list of result keys to fetch, or `["%all%"]`. 
            Defaults to None.

    Returns:
        dict: A populated dictionary containing the requested tracking data. 
            Keys (`parameter`, `metadata`, `result`, `artifacts`) will only be 
            present if they were requested.
    """
    out = {}

    # --- PARAMETERS ---
    if params is not None:
        if "%all%" in params:
            out["parameter"] = select_param_user(engine, search_id=run_names)
        else:
            out["parameter"] = select_param_user(
                engine, search_key=params, search_id=run_names
            )

    # --- METADATA ---
    if meta is not None:
        if "%all%" in meta:
            out["metadata"] = select_metadata_user(engine, search_id=run_names)
        else:
            out["metadata"] = select_metadata_user(
                engine, search_key=meta, search_id=run_names
            )

    # --- RESULTS ---
    if results is not None:
        if "%all%" in results:
            query_res = select_result_user(engine, search_id=run_names)
            out["result"] = query_res[0]
            out["artifacts"] = query_res[1]
        else:
            # Assuming your select_result_user returns a tuple of (results, artifacts) even when searching keys
            query_res = select_result_user(
                engine, search_key=results, search_id=run_names
            )
            out["result"] = query_res[0]
            out["artifacts"] = query_res[1]

    return out


def add_metadata_to_runs(
    engine, run_names: list, notes: list = None, tags: list = None, metadata: dict = None
) -> dict:
    """Appends new notes, tags, or metadata keys to existing simulation runs.

    This acts as the business logic layer: it validates the input data,
    delegates the heavy SQL updates to the database layer, and formats
    the response for the CLI or frontend API.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        run_names (list[str]): A list of run names or UUIDs to update.
        notes (list[str], optional): A list of textual notes to append. Defaults to None.
        tags (list[str], optional): A list of tags to append. Defaults to None.
        metadata (dict, optional): Metadata key/value pairs to merge into the
            runs. Defaults to None.

    Returns:
        dict: A status dictionary containing the operation result, the count of
            updated runs, and lists of the added items.
    """
    # 1. Business Logic & Validation
    if not run_names:
        return {"status": "error", "message": "No run names provided."}

    notes = notes or []
    tags = tags or []
    metadata = metadata or {}

    if not notes and not tags and not metadata:
        return {
            "status": "warning",
            "message": "No notes, tags or metadata provided to add.",
        }

    # 2. Delegate the heavy SQL lifting to the Data Layer
    updated_runs = []
    if notes or tags:
        updated_runs = db_append_note_tag(engine, run_names, notes, tags)
    if metadata:
        updated_meta = db_append_metadata(engine, run_names, metadata)
        updated_runs = list(dict.fromkeys(updated_runs + updated_meta))

    # 3. Process the results
    if not updated_runs:
        return {
            "status": "error",
            "message": f"No runs found matching: {', '.join(run_names)}",
        }

    return {
        "status": "success",
        "updated_count": len(updated_runs),
        "updated_runs": updated_runs,
        "added_notes": len(notes),
        "added_tags": len(tags),
        "added_metadata": len(metadata),
    }


def resolve_run_identifier(engine, token: str):
    """Resolves a user token to a run's uuid: exact name, exact uuid, or prefix.

    Lets users refer to a run by an unambiguous **uuid prefix** (e.g. `a3f9`)
    in addition to its full name or uuid. An exact name wins, then an exact
    uuid, then a uuid that uniquely starts with the token. Ambiguous or
    unknown tokens resolve to None.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        token (str): The name, uuid, or uuid prefix.

    Returns:
        str | None: The matched run's uuid, or None.
    """
    identities = select_run_identities(engine)
    for entry in identities:
        if entry["name"] == token:
            return entry["uuid"]
    for entry in identities:
        if entry["uuid"] == token:
            return entry["uuid"]
    prefix_matches = [
        entry["uuid"] for entry in identities if str(entry["uuid"]).startswith(str(token))
    ]
    return prefix_matches[0] if len(prefix_matches) == 1 else None


def get_run_snapshot(engine, run_name: str) -> dict:
    """Fetches the complete snapshot of a single run, by name, uuid, or prefix.

    This is the data backbone for the interfaces (sillonlab, GUI...): one call
    returns every tracked field of a run, ready to be cached and displayed.
    Artifacts are indexed by their result name for direct lookups. A unique
    uuid prefix is accepted in addition to the full name/uuid.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        run_name (str): The name, uuid, or uuid prefix of the run to load.

    Returns:
        dict | None: The full run row (parameters, results, meta_data, tag,
            note, runtime, status, uuid, ...) with extra `artifacts`,
            `figures` and `analyses` keys mapping names to their linked rows,
            or None if the run does not exist.
    """
    run, artifacts, figures, analyses = select_run_snapshot(engine, run_name)
    if run is None:
        # Fall back to uuid-prefix resolution.
        resolved = resolve_run_identifier(engine, run_name)
        if resolved is not None and resolved != run_name:
            run, artifacts, figures, analyses = select_run_snapshot(engine, resolved)
    if run is None:
        return None
    run["artifacts"] = {artifact["name"]: artifact for artifact in artifacts}
    run["figures"] = {figure["name"]: figure for figure in figures}
    run["analyses"] = {analysis["name"]: analysis for analysis in analyses}
    return run


def load_run_result(storage_root, snapshot: dict, name: str):
    """Loads one result value of a run, wherever it was stored.

    Resolution order matches how the server stored the result:
    1. A dataset saved in the run's HDF5 glob is read back from disk.
    2. A saved artifact resolves to the path of its stored copy.
    3. Anything else (plain value, external path) is returned as stored
       in the database.

    Args:
        storage_root (str | Path): The folder holding the `glob` and
            `artifact` directories of the project.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        name (str): The result name to load.

    Raises:
        LookupError: If the run has no result or artifact with this name.

    Returns:
        Any: The loaded result value.
    """
    if name in snapshot["results"]:
        data = read_glob(storage_root, snapshot["uuid"], "result", name)
        if data is not None:
            return data
        return snapshot["results"][name]

    if name in snapshot["artifacts"]:
        return load_run_artifact(storage_root, snapshot, name)

    raise LookupError(f"Invalid result '{name}' for run '{snapshot['name']}'.")


def load_run_parameter(storage_root, snapshot: dict, name: str):
    """Loads one parameter value of a run, wherever it was stored.

    Lightweight parameters are returned straight from the database. Heavy
    parameter arrays were offloaded to the glob ``parameter`` group at log
    time (the database only holds a marker), so they are read back from disk.

    Args:
        storage_root (str | Path): The folder holding the `glob` directory.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        name (str): The parameter name to load.

    Raises:
        LookupError: If the run has no parameter with this name.

    Returns:
        Any: The loaded parameter value.
    """
    if name not in snapshot["parameters"]:
        raise LookupError(f"Invalid parameter '{name}' for run '{snapshot['name']}'.")

    data = read_glob(storage_root, snapshot["uuid"], "parameter", name)
    if data is not None:
        return data
    return snapshot["parameters"][name]


def load_run_artifact(storage_root, snapshot: dict, name: str) -> Path:
    """Resolves the on-disk location of a saved artifact of a run.

    Args:
        storage_root (str | Path): The folder holding the `artifact` directory.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        name (str): The result name the artifact was logged under.

    Raises:
        LookupError: If the run has no artifact with this name.

    Returns:
        Path: The path to the artifact file, or to its folder if the artifact
            holds several files.
    """
    if name not in snapshot["artifacts"]:
        raise LookupError(f"Invalid artifact '{name}' for run '{snapshot['name']}'.")

    artifact = snapshot["artifacts"][name]
    artifact_dir = (
        Path(storage_root) / "artifact" / str(snapshot["uuid"]) / artifact["path"]
    )
    if artifact_dir.is_dir():
        content = list(artifact_dir.iterdir())
        if len(content) == 1:
            return content[0]
    return artifact_dir


def load_run_source(storage_root, snapshot: dict):
    """Loads the main script source code recorded for a run.

    The source normally lives in the run's HDF5 glob; some runs carry it as
    a plain metadata entry instead, which is used as a fallback.

    Args:
        storage_root (str | Path): The folder holding the `glob` directory.
        snapshot (dict): A run snapshot from `get_run_snapshot`.

    Returns:
        str | None: The recorded source code, or None if it was not tracked.
    """
    source = read_glob(storage_root, snapshot["uuid"], "metadata", "main_source")
    if source is not None:
        return source
    for key in ("sillon.main_script_source", "simply.main_script_source"):
        if key in snapshot["meta_data"]:
            return snapshot["meta_data"][key]
    return None


def _match_conditions(values: dict, conditions: dict) -> bool:
    """True if every condition holds against `values`.

    A condition maps a key to a plain value (equality) or a callable predicate.
    A missing key fails the match.
    """
    for key, condition in conditions.items():
        if key not in values:
            return False
        if callable(condition):
            if not condition(values[key]):
                return False
        elif values[key] != condition:
            return False
    return True


_USER_META_PREFIX = "sillon.user_metadata."


def _meta_get(meta: dict, name: str):
    """Looks up a metadata key, falling back to the user-metadata namespace.

    `sp.add_metadata("dataset", ...)` stores under `sillon.user_metadata.dataset`,
    so a query for the short key `dataset` should still match it.

    Returns (present: bool, value).
    """
    if name in meta:
        return True, meta[name]
    namespaced = _USER_META_PREFIX + name
    if namespaced in meta:
        return True, meta[namespaced]
    return False, None


def _meta_has(meta: dict, name: str) -> bool:
    return _meta_get(meta, name)[0]


def _to_datetime(value):
    """Coerces a datetime or `YYYY-MM-DD[-HH:MM:SS]` string to a datetime, or None."""
    from datetime import datetime

    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d-%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _searchable_columns(entry: dict) -> dict:
    """Flat dict of a run's scalar searchable fields, for `fields={...}` queries.

    This is the single extensibility hook: to make a new top-level field
    searchable (e.g. a future git hash already living in the `hashes` column),
    add it here — no query-engine or API changes needed. The `hashes` JSON
    column is flattened in, so `fields={"git": ...}` works as soon as runs
    record `hashes["git"]`.
    """
    columns = {
        "name": entry.get("name"),
        "date": entry.get("date"),
        "status": entry.get("status"),
        "author": entry.get("author"),
        "hostname": entry.get("hostname"),
        "platform": entry.get("platform"),
        "runtime": entry.get("runtime"),
        "sillonversion": entry.get("sillonversion"),
    }
    columns.update(entry.get("hashes") or {})  # git, source, ... -> top level
    return columns


def match_cheap(
    entry: dict,
    parameters: dict = None,
    metadata: dict = None,
    fields: dict = None,
    has_parameter=None,
    has_metadata=None,
    has_result=None,
    has_analysis=None,
    has_artifact=None,
    has_tag=None,
    before=None,
    after=None,
    storage_root=None,
) -> bool:
    """Tests the database-only (glob-free) criteria against a run.

    Works on either a `select_run_index` row or a `get_run_snapshot` dict — it
    only reads fields present in both (parameters, meta_data, tag, date,
    hashes, columns, and the result/artifact/analysis *names*). This is the
    cheap first phase of a query; no HDF5 file is opened (the only exception is
    a value condition on a glob-stored big-array parameter, which is rare).

    Args mirror the value/presence criteria documented on `query_runs`.

    Returns:
        bool: True if the run satisfies every cheap criterion.
    """
    result_names = set(entry["results"]) | set(entry["artifacts"])

    # --- presence filters ---
    for name in has_parameter or []:
        if name not in entry["parameters"]:
            return False
    for name in has_metadata or []:
        if not _meta_has(entry["meta_data"], name):
            return False
    for name in has_result or []:
        if name not in result_names:
            return False
    for name in has_analysis or []:
        if name not in set(entry["analyses"]):
            return False
    for name in has_artifact or []:
        if name not in set(entry["artifacts"]):
            return False
    for name in has_tag or []:
        if name not in (entry["tag"] or []):
            return False

    # --- date range ---
    if before is not None or after is not None:
        run_dt = _to_datetime(entry.get("date"))
        if run_dt is None:
            return False
        if before is not None and not run_dt < _to_datetime(before):
            return False
        if after is not None and not run_dt > _to_datetime(after):
            return False

    # --- value / predicate filters (DB columns) ---
    if parameters:
        values = {}
        for name in parameters:
            if name not in entry["parameters"]:
                continue
            stored = entry["parameters"][name]
            # Heavy array params keep only a marker in the DB; load the value.
            if isinstance(stored, dict) and stored.get("__sillon_array_ref__"):
                values[name] = load_run_parameter(storage_root, entry, name)
            else:
                values[name] = stored
        if not _match_conditions(values, parameters):
            return False

    if metadata:
        values = {}
        for name in metadata:
            present, value = _meta_get(entry["meta_data"], name)
            if present:
                values[name] = value
        if not _match_conditions(values, metadata):
            return False

    if fields:
        if not _match_conditions(_searchable_columns(entry), fields):
            return False

    return True


def match_heavy(storage_root, snapshot: dict, results: dict = None, analyses: dict = None) -> bool:
    """Tests result/analysis value conditions, reading the run's glob once.

    All needed datasets are read in a single file open (`read_glob_many`);
    non-glob results (artifacts, plain DB values) fall back to `load_run_result`.

    Args:
        storage_root (str | Path): The project storage root.
        snapshot (dict): A full run snapshot from `get_run_snapshot`.
        results (dict, optional): Result value/predicate conditions.
        analyses (dict, optional): Analysis value/predicate conditions.

    Returns:
        bool: True if the run satisfies every heavy criterion.
    """
    result_names = set(snapshot["results"]) | set(snapshot["artifacts"])

    reads = []
    if results:
        reads += [("result", n) for n in results if n in result_names]
    if analyses:
        reads += [("analysis", n) for n in analyses if n in snapshot["analyses"]]
    data = read_glob_many(storage_root, snapshot["uuid"], reads)

    if results:
        values = {}
        for name in results:
            if name not in result_names:
                continue  # missing -> excluded by _match_conditions
            value = data.get(("result", name))
            if value is None:  # artifact result or plain DB value
                value = load_run_result(storage_root, snapshot, name)
            values[name] = value
        if not _match_conditions(values, results):
            return False

    if analyses:
        values = {}
        for name in analyses:
            if name not in snapshot["analyses"]:
                continue
            value = data.get(("analysis", name))
            if value is None:
                value = load_run_analysis(storage_root, snapshot, name)
            values[name] = value
        if not _match_conditions(values, analyses):
            return False

    return True


def match_run(
    storage_root,
    snapshot: dict,
    parameters: dict = None,
    results: dict = None,
    analyses: dict = None,
    metadata: dict = None,
    fields: dict = None,
    has_parameter=None,
    has_metadata=None,
    has_result=None,
    has_analysis=None,
    has_artifact=None,
    has_tag=None,
    before=None,
    after=None,
) -> bool:
    """Tests all query criteria against an in-memory run snapshot.

    Cheap criteria are checked first (so the glob is only touched when a run
    passes them and there are result/analysis value conditions). Used by
    `RunCollection.where`, which already holds full snapshots in memory.
    """
    if not match_cheap(
        snapshot,
        parameters=parameters,
        metadata=metadata,
        fields=fields,
        has_parameter=has_parameter,
        has_metadata=has_metadata,
        has_result=has_result,
        has_analysis=has_analysis,
        has_artifact=has_artifact,
        has_tag=has_tag,
        before=before,
        after=after,
        storage_root=storage_root,
    ):
        return False

    if (results or analyses) and not match_heavy(storage_root, snapshot, results, analyses):
        return False

    return True


def query_runs(
    engine,
    storage_root=None,
    parameters: dict = None,
    results: dict = None,
    analyses: dict = None,
    metadata: dict = None,
    fields: dict = None,
    has_parameter=None,
    has_metadata=None,
    has_result=None,
    has_analysis=None,
    has_artifact=None,
    has_tag=None,
    before=None,
    after=None,
) -> list:
    """Finds the runs matching a set of criteria, in two phases for speed.

    Phase 1 (cheap, glob-free): a single bulk index fetch
    (`select_run_index`) is filtered in memory on the database-only criteria —
    parameter and metadata value/predicate conditions, generic column
    conditions (`fields`), date range (`before`/`after`), and all presence
    filters (`has_parameter`, `has_metadata`, `has_result`, `has_analysis`,
    `has_artifact`, `has_tag`).

    Phase 2 (heavy, only when `results`/`analyses` value conditions are given):
    for each survivor of phase 1, its glob is opened once to evaluate the
    result/analysis value conditions. So globs are read only for runs that
    already passed the cheap filters, and never for pure cheap queries.

    Value conditions (`parameters`, `results`, `analyses`, `metadata`, `fields`)
    are dicts mapping a name to an expected value (equality) or a callable
    predicate. Presence filters are lists of names. All criteria combine with
    logical AND; with no criteria every run is returned.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        storage_root (str | Path, optional): The project storage root; required
            when filtering on result or analysis values.
        parameters (dict, optional): Parameter value/predicate conditions.
        results (dict, optional): Result value/predicate conditions.
        analyses (dict, optional): Analysis value/predicate conditions.
        metadata (dict, optional): Metadata value/predicate conditions.
        fields (dict, optional): Top-level column value/predicate conditions.
        has_parameter (list[str], optional): Parameter names that must exist.
        has_metadata (list[str], optional): Metadata names that must exist.
        has_result (list[str], optional): Result/artifact names that must exist.
        has_analysis (list[str], optional): Analysis names that must exist.
        has_artifact (list[str], optional): Artifact names that must exist.
        has_tag (list[str], optional): Tags the run must have.
        before (datetime | str, optional): Exclusive upper date bound
            (a `YYYY-MM-DD` string parses to midnight).
        after (datetime | str, optional): Exclusive lower date bound.

    Returns:
        list[str]: The names of the matching runs.
    """
    survivors = [
        entry
        for entry in select_run_index(engine)
        if match_cheap(
            entry,
            parameters=parameters,
            metadata=metadata,
            fields=fields,
            has_parameter=has_parameter,
            has_metadata=has_metadata,
            has_result=has_result,
            has_analysis=has_analysis,
            has_artifact=has_artifact,
            has_tag=has_tag,
            before=before,
            after=after,
            storage_root=storage_root,
        )
    ]

    # Pure cheap query: no glob reads at all.
    if not (results or analyses):
        return [entry["name"] for entry in survivors]

    # Heavy phase: open globs only for the survivors of the cheap filters.
    matching = []
    for entry in survivors:
        snapshot = get_run_snapshot(engine, entry["uuid"])
        if snapshot is not None and match_heavy(storage_root, snapshot, results, analyses):
            matching.append(snapshot["name"])
    return matching


def fetch_run_result(storage_root, snapshot: dict, name: str, dest=None) -> Path:
    """Fetches a result or artifact of a run as a file on disk.

    Artifacts are copied to the destination. Glob results are loaded and
    saved as a `.npy` file (or `.txt` for plain strings). This is the engine
    behind "grab this result and put it in my working directory".

    Args:
        storage_root (str | Path): The project storage root.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        name (str): The result, artifact, or figure name to fetch.
        dest (str | Path, optional): The destination directory. Defaults to
            the current working directory.

    Raises:
        LookupError: If the run has no result with this name.

    Returns:
        Path: The path of the fetched copy.
    """
    import numpy as np

    dest = Path(dest or Path.cwd())
    dest.mkdir(parents=True, exist_ok=True)

    # Artifacts and figures are already files: copy them over.
    if name in snapshot["artifacts"] or name in snapshot["figures"]:
        if name in snapshot["artifacts"]:
            source = load_run_artifact(storage_root, snapshot, name)
        else:
            source = load_run_figure(storage_root, snapshot, name)
        target = dest / source.name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy(source, target)
        return target

    # Glob results and plain values are materialized.
    value = load_run_result(storage_root, snapshot, name)
    if isinstance(value, str):
        target = dest / f"{name}.txt"
        target.write_text(value)
    else:
        target = dest / f"{name}.npy"
        np.save(target, np.asarray(value))
    return target


def _disk_size(path: Path) -> int:
    """Returns the size in bytes of a file or of a directory tree."""
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return 0


def get_run_sizes(storage_root, snapshot: dict) -> dict:
    """Measures the storage footprint of every stored item of a run.

    Args:
        storage_root (str | Path): The project storage root.
        snapshot (dict): A run snapshot from `get_run_snapshot`.

    Returns:
        dict: Mapping of item names to `{"kind": str, "bytes": int}` where
            kind is one of "result", "artifact", "figure", "analysis".
    """
    sizes = {}
    uuid = snapshot["uuid"]

    for name, nbytes in glob_sizes(storage_root, uuid, "result").items():
        sizes[name] = {"kind": "result", "bytes": nbytes}
    for name, nbytes in glob_sizes(storage_root, uuid, "analysis").items():
        sizes[name] = {"kind": "analysis", "bytes": nbytes}

    for name in snapshot["artifacts"]:
        path = load_run_artifact(storage_root, snapshot, name)
        sizes[name] = {"kind": "artifact", "bytes": _disk_size(path)}
    for name in snapshot["figures"]:
        path = load_run_figure(storage_root, snapshot, name)
        sizes[name] = {"kind": "figure", "bytes": _disk_size(path)}

    return sizes


def export_run(storage_root, snapshot: dict, dest=None, format: str = "npz") -> dict:
    """Exports the stored data of a run into a portable file.

    Formats:
        - "npz": every glob result and analysis in one compressed numpy file.
        - "npy": a folder with one `.npy` file per result/analysis.
        - "hdf5": a standalone HDF5 file with the result and analysis groups,
          plus the parameters and run identity stored as root attributes
          (the closest thing to a zip of everything).

    Args:
        storage_root (str | Path): The project storage root.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        dest (str | Path, optional): Output file (or folder for "npy").
            Defaults to `<run_name>_export.<ext>` in the current directory.
        format (str): One of "npz", "npy", "hdf5". Defaults to "npz".

    Raises:
        ValueError: If the format is unknown.

    Returns:
        dict: `{"path": Path, "exported": [names], "skipped": [names]}`.
    """
    import json

    import numpy as np

    if format not in ("npz", "npy", "hdf5"):
        raise ValueError(f"Unknown export format '{format}' (npz, npy, hdf5).")

    # Collect everything loadable: results then analyses.
    # Strings stay as-is (h5py stores them natively); the rest becomes arrays.
    data, skipped = {}, []
    for name in snapshot["results"]:
        value = load_run_result(storage_root, snapshot, name)
        try:
            data[name] = value if isinstance(value, str) else np.asarray(value)
        except Exception:
            skipped.append(name)
    for name in snapshot["analyses"]:
        value = read_glob(storage_root, snapshot["uuid"], "analysis", name)
        if value is not None:
            data[f"analysis.{name}"] = np.asarray(value)

    run_name = snapshot["name"]
    if format == "npz":
        target = Path(dest or f"{run_name}_export.npz")
        target.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(target, **data)

    elif format == "npy":
        target = Path(dest or f"{run_name}_export")
        target.mkdir(parents=True, exist_ok=True)
        for name, value in data.items():
            np.save(target / f"{name}.npy", value)

    else:  # hdf5
        import h5py

        target = Path(dest or f"{run_name}_export.hdf5")
        target.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(target, "w") as out:
            for name, value in data.items():
                if name.startswith("analysis."):
                    out.create_dataset(f"analysis/{name[len('analysis.'):]}", data=value)
                else:
                    out.create_dataset(f"result/{name}", data=value)
            out.attrs["run_name"] = run_name
            out.attrs["run_uuid"] = str(snapshot["uuid"])
            out.attrs["date"] = str(snapshot["date"])
            out.attrs["parameters"] = json.dumps(snapshot["parameters"])
            out.attrs["tags"] = json.dumps(snapshot["tag"] or [])

    return {"path": target, "exported": list(data.keys()), "skipped": skipped}


def build_run_report(engine, storage_root, snapshot: dict) -> dict:
    """Assembles a self-contained, human- and machine-readable run summary.

    Gathers everything needed to understand "what a run used and did" later:
    parameters, results (with sizes), metadata, tags, notes, figures with
    their data provenance, analyses, and execution context. Pure data — no
    files are written here.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        storage_root (str | Path): The project storage root.
        snapshot (dict): A run snapshot from `get_run_snapshot`.

    Returns:
        dict: A structured manifest of the run.
    """
    sizes = get_run_sizes(storage_root, snapshot)

    figures = {
        name: {
            "used": (figure["meta"] or {}).get("used", []),
            "caption": (figure["meta"] or {}).get("caption"),
            "meta": figure["meta"] or {},
        }
        for name, figure in snapshot["figures"].items()
    }
    analyses = {
        name: {"meta": analysis["meta"] or {}, "size": sizes.get(name, {}).get("bytes")}
        for name, analysis in snapshot["analyses"].items()
    }

    return {
        "name": snapshot["name"],
        "uuid": snapshot["uuid"],
        "date": snapshot["date"],
        "status": snapshot["status"],
        "runtime": snapshot["runtime"],
        "project": snapshot.get("project"),
        "author": snapshot.get("author"),
        "hostname": snapshot.get("hostname"),
        "platform": snapshot.get("platform"),
        "sillonversion": snapshot.get("sillonversion"),
        "parameters": snapshot["parameters"],
        "results": {
            name: {"bytes": info["bytes"], "kind": info["kind"]}
            for name, info in sizes.items()
        },
        "metadata": snapshot["meta_data"],
        "tags": snapshot["tag"] or [],
        "notes": snapshot["note"] or [],
        "figures": figures,
        "analyses": analyses,
    }


def _render_report_markdown(report: dict) -> str:
    """Renders a run report manifest as a readable markdown document."""
    lines = [
        f"# Run report — {report['name']}",
        "",
        f"- **UUID:** {report['uuid']}",
        f"- **Date:** {report['date']}",
        f"- **Status:** {report['status']}",
        f"- **Runtime:** {report['runtime']}",
        f"- **Project:** {report.get('project')}",
        f"- **Author:** {report.get('author')}",
        f"- **Host / platform:** {report.get('hostname')} / {report.get('platform')}",
        f"- **sillon version:** {report.get('sillonversion')}",
        "",
        "## Parameters",
        "",
    ]
    if report["parameters"]:
        lines += [f"- `{key}` = `{value}`" for key, value in report["parameters"].items()]
    else:
        lines.append("_none_")

    lines += ["", "## Results", ""]
    if report["results"]:
        lines += [
            f"- `{name}` ({info['kind']}, {info['bytes']} bytes)"
            for name, info in report["results"].items()
        ]
    else:
        lines.append("_none_")

    if report["figures"]:
        lines += ["", "## Figures", ""]
        for name, figure in report["figures"].items():
            used = ", ".join(figure["used"]) or "—"
            caption = f" — {figure['caption']}" if figure.get("caption") else ""
            lines.append(f"- `{name}` (built from: {used}){caption}")

    if report["analyses"]:
        lines += ["", "## Analyses", ""]
        for name, analysis in report["analyses"].items():
            comment = analysis["meta"].get("comment")
            lines.append(f"- `{name}`" + (f" — {comment}" if comment else ""))

    if report["tags"]:
        lines += ["", "## Tags", "", ", ".join(report["tags"])]
    if report["notes"]:
        lines += ["", "## Notes", ""]
        lines += [f"- {note}" for note in report["notes"]]

    lines.append("")
    return "\n".join(lines)


def export_run_report(engine, storage_root, snapshot: dict, dest=None, with_data: bool = False) -> Path:
    """Exports a run's context as a self-contained zip bundle.

    The bundle answers "what did this run use and do" and is safe to archive
    or share. It contains:
        - `manifest.json` — the full structured report,
        - `report.md` — a human-readable summary,
        - `source/main.py` — the run's recorded entry script (if available),
        - `data.hdf5` — all results and analyses (only when `with_data=True`).

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        storage_root (str | Path): The project storage root.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        dest (str | Path, optional): Output zip path. Defaults to
            `<run_name>_report.zip` in the current directory.
        with_data (bool): Also embed the run's data as HDF5. Defaults to False.

    Returns:
        Path: The path of the written zip bundle.
    """
    import json
    import tempfile
    import zipfile

    report = build_run_report(engine, storage_root, snapshot)
    dest = Path(dest or f"{snapshot['name']}_report.zip")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps(report, indent=2, default=str))
        bundle.writestr("report.md", _render_report_markdown(report))

        source = load_run_source(storage_root, snapshot)
        if source:
            bundle.writestr("source/main.py", source)

        if with_data:
            with tempfile.TemporaryDirectory() as tmp:
                data_path = export_run(
                    storage_root, snapshot, Path(tmp) / "data.hdf5", format="hdf5"
                )["path"]
                bundle.write(data_path, "data.hdf5")

    return dest


def prune_runs(
    engine,
    storage_root,
    run_names=None,
    before=None,
    keep_metadata: bool = True,
) -> dict:
    """Frees disk space by deleting the stored data of selected runs.

    Targets runs either by name/uuid (`run_names`) or by age (`before`). For
    each target, the `glob/`, `artifact/` and `figure/` folders are removed.
    With `keep_metadata` the database rows are preserved (so the run still
    shows up in queries, just without its heavy data); otherwise the rows are
    deleted too.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        storage_root (str | Path): The project storage root.
        run_names (list[str], optional): Run names or uuids to prune.
        before (datetime, optional): Prune runs created strictly before this
            datetime (run dates are stored as `%Y-%m-%d-%H:%M:%S`).
        keep_metadata (bool): Keep the database rows. Defaults to True.

    Returns:
        dict: `{"status", "pruned": [names], "freed_bytes": int, "kept_metadata": bool}`.
            Status is "error" if no selector is given (refuses to prune all).
    """
    import shutil as _shutil
    from datetime import datetime

    if not run_names and before is None:
        return {
            "status": "error",
            "message": "Refusing to prune: specify run_names or a 'before' cutoff.",
        }

    storage_root = Path(storage_root)
    selectors = set(run_names or [])
    targets = []
    for run in select_run_identities(engine):
        selected = run["name"] in selectors or run["uuid"] in selectors
        if before is not None and run["date"]:
            try:
                if datetime.strptime(run["date"], "%Y-%m-%d-%H:%M:%S") < before:
                    selected = True
            except ValueError:
                pass
        if selected:
            targets.append(run)

    freed = 0
    pruned = []
    for run in targets:
        for group in ("glob", "artifact", "figure"):
            folder = storage_root / group / str(run["uuid"])
            if folder.exists():
                freed += _disk_size(folder)
                _shutil.rmtree(folder, ignore_errors=True)
        pruned.append(run["name"])

    if not keep_metadata and pruned:
        db_delete_runs(engine, [run["uuid"] for run in targets])

    return {
        "status": "success",
        "pruned": pruned,
        "freed_bytes": freed,
        "kept_metadata": keep_metadata,
    }


def delete_run(engine, storage_root, run_name) -> dict:
    """Permanently deletes a single run: its stored data and its database row.

    Removes the run's `glob/`, `artifact/` and `figure/` folders and deletes
    the `SimulationTable` row along with its linked artifacts, figures, and
    analyses. This is the irreversible "I don't want this run anymore" action
    (unlike `prune_runs(..., keep_metadata=True)`, which only frees disk).

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        storage_root (str | Path): The project storage root.
        run_name (str): The name or uuid of the run to delete.

    Returns:
        dict: `{"status": "success", "deleted": str, "freed_bytes": int}`, or
            `{"status": "error", "message": str}` if the run does not exist.
    """
    resolved = resolve_run_identifier(engine, run_name) or run_name
    result = prune_runs(
        engine, storage_root, run_names=[resolved], keep_metadata=False
    )
    if not result["pruned"]:
        return {"status": "error", "message": f"Run '{run_name}' not found."}
    return {
        "status": "success",
        "deleted": result["pruned"][0],
        "freed_bytes": result["freed_bytes"],
    }


def rename_run(engine, run_name: str, new_name: str) -> dict:
    """Renames a run, rejecting the rename if the new name is already taken.

    Storage is uuid-based, so this is a pure metadata update.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        run_name (str): The current name, uuid, or uuid prefix of the run.
        new_name (str): The desired new name.

    Returns:
        dict: `{"status": "success", "old": ..., "new": ...}`, or
            `{"status": "error", "message": ...}` if the run is missing or the
            new name clashes with an existing run.
    """
    resolved = resolve_run_identifier(engine, run_name)
    if resolved is None:
        return {"status": "error", "message": f"Run '{run_name}' not found."}
    if next_available_name(engine, new_name) != new_name:
        return {"status": "error", "message": f"The name '{new_name}' is already taken."}

    renamed = db_rename_run(engine, resolved, new_name)
    return {"status": "success", "old": renamed["old"], "new": renamed["new"]}


def find_by_hash(engine, file_or_hash) -> list:
    """Finds which run(s) own a file, by content hash.

    If given an existing file path, the file is hashed (`get_hash`); otherwise
    the argument is treated as a hash directly. Looks the hash up across the
    stored figures and artifacts.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        file_or_hash (str | Path): A file path or a SHA-256 hash.

    Returns:
        list[dict]: One `{run_name, run_uuid, kind, name}` per match.
    """
    import os

    token = str(file_or_hash)
    if os.path.isfile(token):
        token = get_hash(token)
    return select_by_hash(engine, token)


def load_run_figure(storage_root, snapshot: dict, name: str) -> Path:
    """Resolves the on-disk location of a figure logged during a run.

    Args:
        storage_root (str | Path): The folder holding the `figure` directory.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        name (str): The name the figure was logged under.

    Raises:
        LookupError: If the run has no figure with this name.

    Returns:
        Path: The path to the figure file.
    """
    if name not in snapshot["figures"]:
        raise LookupError(f"Invalid figure '{name}' for run '{snapshot['name']}'.")

    figure = snapshot["figures"][name]
    figure_dir = Path(storage_root) / "figure" / str(snapshot["uuid"]) / figure["path"]
    if figure_dir.is_dir():
        content = list(figure_dir.iterdir())
        if len(content) == 1:
            return content[0]
    return figure_dir


def add_run_analysis(
    engine, storage_root, snapshot: dict, name: str, data, info: dict = None
) -> dict:
    """Attaches post-processed data to an already finished run.

    The data is written into the run's HDF5 glob under the `analysis` group
    and a row linking it to the run (with hash and free-form context) is
    inserted in the database, so the processed data can be reloaded later
    exactly like a native result.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        storage_root (str | Path): The project storage root.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        name (str): The analysis name.
        data (Any): The processed data to store (h5py compatible).
        info (dict, optional): Free-form context (inputs used, comment...).

    Returns:
        dict: The inserted analysis row.
    """
    hsh = append_glob(storage_root, snapshot["uuid"], "analysis", name, data)
    return db_insert_analysis(
        engine, snapshot["id"], name, pointer=name, hsh=hsh, meta=info or {}
    )


def load_run_analysis(storage_root, snapshot: dict, name: str):
    """Loads back a post-processed analysis attached to a run.

    Args:
        storage_root (str | Path): The project storage root.
        snapshot (dict): A run snapshot from `get_run_snapshot`.
        name (str): The analysis name to load.

    Raises:
        LookupError: If no analysis with this name is stored for the run.

    Returns:
        Any: The stored analysis data.
    """
    data = read_glob(storage_root, snapshot["uuid"], "analysis", name)
    if data is None:
        raise LookupError(f"Invalid analysis '{name}' for run '{snapshot['name']}'.")
    return data


def compare(engine, run_id1, run_id2) -> dict:
    """Compares two simulation runs and returns their differences.

    Instantiates two `Reference` objects from the database and utilizes the 
    `Diffref` engine to calculate the exact changes in parameters, context, 
    and source code between the original run and the target run.

    Args:
        engine (Engine): The active SQLAlchemy database engine.
        run_id1 (str): The identifier (name or UUID) of the baseline run.
        run_id2 (str): The identifier (name or UUID) of the target run to compare.

    Returns:
        dict: A dictionary containing the diff mappings.
            Format:
            ```python
            {
                "status": "success",
                "diff_param": dict,       # Parameter added/removed/changed metrics
                "diff_status": tuple,     # Status difference (if any)
                "diff_runtime": tuple,    # Runtime difference (if any)
                "diff_source": str        # Unified text diff of the source code
            }
            ```
    """
    ref1 = Reference(engine=engine, run_name=run_id1)
    ref2 = Reference(engine=engine, run_name=run_id2)
    diff_engine = Diffref(ref1, ref2)

    return {
        "status": "success",
        "diff_param": diff_engine.diff_parameters,
        "diff_status": diff_engine.diff_status,
        "diff_runtime": diff_engine.diff_runtime,
        "diff_source": diff_engine.diff_source,
    }
