from pathlib import Path
from typing import Optional

from silloncore.project_paths import (
    resolve_storage_root,
    resolve_engine,
    resolve_project_name,
)
from silloncore.engine import (
    get_project_context,
    get_run_details,
    add_metadata_to_runs,
    query_runs,
    delete_run as engine_delete_run,
    rename_run as engine_rename_run,
    trace as engine_trace,
    get_code_versions as engine_code_versions,
    prune_runs as engine_prune,
    get_project_context,
    diff as engine_diff,
    diff_across_runs as engine_diff_across,
    find_similar_runs as engine_find_similar,
)

from sillonlab.display import print_context
from sillonlab.run import Run, RunCollection


def _as_list(value) -> Optional[list]:
    """Normalizes a user argument to a list (str -> [str], None -> None)."""
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


class Project:
    """The entry point of sillonlab: a loaded sillon project.

    Wraps the silloncore engine so logged runs can be explored from a python
    script or a jupyter notebook, the same way silloncli does from the shell.

    Example:
        ```python
        import sillonlab as sl

        project = sl.load_project("path/to/project")
        runs = project.runs()                # RunCollection of all runs
        run = project.get("integration_alpha")
        run.parameters                       # {"learning_rate": 0.01, ...}
        run.load_result("final_loss")        # read back from the HDF5 glob
        ```

    Attributes:
        path (Path): The root path of the project.
        storage_root (Path): The folder holding the database, glob and
            artifact storage (the `.sillon` folder by default).
        engine (Engine): The SQLAlchemy engine connected to the project
            database.
    """

    def __init__(self, project_path=None) -> None:
        """Loads a sillon project from disk.

        Args:
            project_path (str | Path, optional): The project root (the folder
                containing `.sillon`). Defaults to the current working
                directory.

        Raises:
            FileNotFoundError: If no `.sillon` directory or database is found.
        """
        self.path = Path(project_path or Path.cwd()).expanduser().resolve()
        self._sillon_dir = self.path / ".sillon"
        if not self._sillon_dir.exists():
            raise FileNotFoundError(
                f"Not a sillon project: no .sillon directory in {self.path}"
            )
        # Storage-root and engine resolution is shared with the CLI (silloncore).
        self.storage_root = resolve_storage_root(self.path)
        self.engine = resolve_engine(self.path)
        # The project's own name, from its config rather than this machine's
        # registry, so it survives being copied or moved. "" when unset.
        self.name = resolve_project_name(self.path)

    # ---------------------------------------------------------
    # Run access
    # ---------------------------------------------------------

    def show(self, *run_names: str) -> None:
        """Pretty-prints the project's runs, like `sillon list` does.

        With no argument, an overview table of every run. With run names, a
        detail card per run. Works in a terminal and in a jupyter notebook.

        Args:
            *run_names (str): Optional run names to target.
        """
        print_context(
            get_project_context(self.engine, list(run_names)),
            project_name=self.name or self.path.name,
        )

    def runs(self) -> RunCollection:
        """Loads all the runs of the project.

        Returns:
            RunCollection: Lazy `Run` handles, sorted by timestamp.
        """
        overview = get_project_context(self.engine)
        return RunCollection(
            [
                Run(
                    name=run_data["name"],
                    engine=self.engine,
                    storage_root=self.storage_root,
                    context=run_data,
                )
                for run_data in overview["runs"]
            ]
        )

    def query(
        self,
        has_parameter=None,
        has_metadata=None,
        has_result=None,
        has_analysis=None,
        has_artifact=None,
        has_tag=None,
        tags=None,
        parameters=None,
        metadata=None,
        results=None,
        analyses=None,
        fields=None,
        before=None,
        after=None,
        **param_conditions,
    ) -> RunCollection:
        """Finds the runs matching value/predicate and presence criteria.

        Value conditions map a name to a plain value (equality) or a callable
        predicate, and can target `parameters`, `metadata`, `results`, or
        `analyses`. Bare keyword arguments are a shorthand for parameter
        conditions. `fields` filters on top-level columns (status, author,
        git hash, ...). `before`/`after` filter on the run date. Presence
        filters (`has_*`, `tags`) keep only runs that have the named item.

        Cheap criteria (parameters, metadata, tags, date, fields, presence) are
        resolved entirely from the database; result/analysis value conditions
        read the glob, but only for runs that already passed the cheap filters.

        Example:
            ```python
            project.query(optimizer="adam")                       # param equality
            project.query(learning_rate=lambda lr: lr < 0.1)      # param predicate
            project.query(metadata={"sillon.language": "python"})
            project.query(tags="baseline", after="2026-06-01")
            project.query(fields={"status": "SUCCESS"})
            project.query(results={"final_loss": lambda v: v < 0.05})
            project.query(tags="prod", results={"loss": lambda v: v < 0.1})
            ```

        Args:
            has_parameter (str | list, optional): Parameter name(s) that must exist.
            has_metadata (str | list, optional): Metadata name(s) that must exist.
            has_result (str | list, optional): Result/artifact name(s) that must exist.
            has_analysis (str | list, optional): Analysis name(s) that must exist.
            has_artifact (str | list, optional): Artifact name(s) that must exist.
            has_tag (str | list, optional): Tag(s) the run must have.
            tags (str | list, optional): Alias for `has_tag`.
            parameters (dict, optional): Parameter value/predicate conditions.
            metadata (dict, optional): Metadata value/predicate conditions.
            results (dict, optional): Result value/predicate conditions.
            analyses (dict, optional): Analysis value/predicate conditions.
            fields (dict, optional): Conditions on top-level columns (e.g.
                `{"status": "SUCCESS", "author": "doph"}`).
            before (datetime | str, optional): Keep runs created before this date.
            after (datetime | str, optional): Keep runs created after this date.
            **param_conditions: Shorthand parameter value/predicate conditions.

        Returns:
            RunCollection: The matching runs.
        """
        merged_parameters = {**(parameters or {}), **param_conditions} or None
        merged_tags = (_as_list(has_tag) or []) + (_as_list(tags) or [])
        names = query_runs(
            self.engine,
            self.storage_root,
            parameters=merged_parameters,
            metadata=metadata,
            results=results,
            analyses=analyses,
            fields=fields,
            has_parameter=_as_list(has_parameter),
            has_metadata=_as_list(has_metadata),
            has_result=_as_list(has_result),
            has_analysis=_as_list(has_analysis),
            has_artifact=_as_list(has_artifact),
            has_tag=merged_tags or None,
            before=before,
            after=after,
        )
        return RunCollection(
            [
                Run(name=name, engine=self.engine, storage_root=self.storage_root)
                for name in names
            ]
        )

    def get(self, run_name: str) -> Run:
        """Loads a single run by name or uuid.

        Args:
            run_name (str): The name or uuid of the run.

        Raises:
            LookupError: If the run does not exist in the project database.

        Returns:
            Run: The loaded run handle.
        """
        run = Run(name=run_name, engine=self.engine, storage_root=self.storage_root)
        run._load_snapshot()  # Fail early if the run does not exist
        return run

    # ---------------------------------------------------------
    # Run annotation and comparison
    # ---------------------------------------------------------

    def add(self, run_names, notes=None, tags=None) -> dict:
        """Appends notes or tags to existing runs, like `sillon add`.

        Args:
            run_names (str | list): The run name(s) to annotate.
            notes (str | list, optional): Note(s) to append.
            tags (str | list, optional): Tag(s) to append.

        Returns:
            dict: The engine status payload of the operation.
        """
        return add_metadata_to_runs(
            self.engine,
            run_names=_as_list(run_names),
            notes=_as_list(notes),
            tags=_as_list(tags),
        )

    def delete_run(self, run) -> dict:
        """Permanently deletes a run (its stored data and database row).

        Args:
            run (Run | str): A `Run` handle, or the run name/uuid to delete.

        Returns:
            dict: `{"status": "success", "deleted": str, "freed_bytes": int}`,
                or an error status if the run does not exist.
        """
        name = run.name if isinstance(run, Run) else run
        return engine_delete_run(self.engine, self.storage_root, name)

    def rename(self, run, new_name: str) -> dict:
        """Renames a run, rejecting the rename if `new_name` is already taken.

        Args:
            run (Run | str): A `Run` handle, or the run name/uuid to rename.
            new_name (str): The new run name.

        Returns:
            dict: `{"status": "success", "old": ..., "new": ...}` or an error
                status.
        """
        name = run.name if isinstance(run, Run) else run
        return engine_rename_run(self.engine, name, new_name)

    def trace(self, file_or_hash) -> list:
        """Finds which run(s) own a file, by its content hash.

        Pass a file path (it gets hashed) or a hash string. Useful to trace a
        stray figure/artifact back to the run that produced it.

        Args:
            file_or_hash (str | Path): A file path or a SHA-256 hash.

        Returns:
            list[dict]: One `{run_name, run_uuid, kind, name}` per match.
        """
        return engine_trace(self.engine, file_or_hash)

    def diff(self, run_name1: str, run_name2: str, max_bytes: int = None) -> dict:
        """Compares two runs: parameters, code, results and context.

        Richer than `compare`, which only reaches parameters, status, runtime
        and a source-text diff. This also reports whether the code differed *in
        logic* or only in a tuned constant, and whether the results moved —
        arrays by shape, dtype and hash rather than element by element.

        Example:
            ```python
            d = project.diff("baseline", "refined")
            d["code"]["same_logic"]          # was this a fair comparison?
            d["parameters"]["changed"]       # {key: {old, new, delta_pct}}
            d["results"]["rmse"]["delta_pct"]
            ```

        Args:
            run_name1 (str): Baseline run name, uuid, or uuid prefix.
            run_name2 (str): Target run.
            max_bytes (int, optional): Largest result to load for comparison.
                Bigger ones are compared by shape and dtype only.

        Raises:
            LookupError: If either run cannot be found.

        Returns:
            dict: `{"runs", "parameters", "code", "results", "context"}`.
        """
        return engine_diff(self.engine, self.storage_root, run_name1, run_name2, max_bytes)

    def diff_across(self, run_names=None, **query) -> dict:
        """What varies, and what is held fixed, across a set of runs.

        The question a sweep leaves behind months later: which knobs were
        actually turned?

        Example:
            ```python
            project.diff_across(has_tag="sweep")
            # {"varying": {"degree": [1,2,3,4,5], "ridge": [0.0, 0.1]},
            #  "constant": {"seed": 7, "solver": "lstsq"}, ...}
            ```

        Args:
            run_names (list[str], optional): Explicit runs. Omit to use every
                run matching the filters.
            **query: Cheap filters (`has_tag`, `fields`, `parameters`, ...).

        Returns:
            dict: `{"run_count", "varying", "constant", "logic_versions", "runs"}`.
        """
        return engine_diff_across(self.engine, run_names, **query)

    def like(self, run, limit: int = 10) -> list:
        """The runs most similar to this one, by shared configuration.

        "Did I do something close to this?" — more useful than an exact-match
        check, which only fires on a perfect repeat and tells you nothing about
        the near misses.

        Example:
            ```python
            for match in project.like("happy_perlman"):
                print(f"{match['score']:.0%}", match["name"], match["changes"])
            ```

        Args:
            run (str | Run): The run to compare against.
            limit (int): How many matches to return.

        Raises:
            LookupError: If the run cannot be found.

        Returns:
            list[dict]: `{"name", "uuid", "score", "differing", "changes",
                "same_code"}`, best match first.
        """
        name = run.name if isinstance(run, Run) else run
        return engine_find_similar(self.engine, name, limit)["matches"]

    def versions(self) -> list:
        """The project's runs grouped by the code version that produced them.

        The notebook counterpart of `sillon versions`. A version covers the
        entry script and your own modules, hashed so a tuned constant does not
        read as a change — see the Code versions guide.

        Example:
            ```python
            for group in project.versions():
                print(group["logic_version"][:8], group["run_count"])

            current = project.versions()[0]["logic_version"]
            clean = project.query(fields={"logic_version": current})
            ```

        Returns:
            list[dict]: `{"logic_version", "run_count", "runs", "first_seen",
                "last_seen", "constant_variants", "files", "partial"}`, most
                recent first.
        """
        return engine_code_versions(self.engine)

    def prune(self, run_names=None, before=None, keep_metadata: bool = True) -> dict:
        """Frees disk space by deleting the stored data of selected runs.

        With `keep_metadata` the database rows survive, so you still know what
        you ran and with which parameters — only the heavy data goes. Set it
        False to remove the rows too, which is irreversible.

        Requires a scope: pass `run_names` or `before`, never neither.

        Args:
            run_names (list[str], optional): Runs to prune.
            before (str, optional): Prune runs older than this date or age.
            keep_metadata (bool): Keep the database rows. Defaults to True.

        Returns:
            dict: `{"pruned", "freed_bytes", ...}`.
        """
        return engine_prune(
            self.engine, self.storage_root,
            run_names=run_names, before=before, keep_metadata=keep_metadata,
        )

    # ---------------------------------------------------------
    # Container protocol
    # ---------------------------------------------------------

    def __getitem__(self, key) -> Run:
        if isinstance(key, str):
            return self.get(key)
        return self.runs()[key]

    def __len__(self):
        return len(self.runs())

    def __iter__(self):
        return iter(self.runs())

    def __repr__(self):
        label = self.name or self.path.name
        return f"Project({label} @ {self.path})"


def load_project(project_path=None) -> Project:
    """Loads a sillon project from a path (defaults to the current directory).

    Args:
        project_path (str | Path, optional): The project root containing the
            `.sillon` directory.

    Returns:
        Project: The loaded project.
    """
    return Project(project_path)
