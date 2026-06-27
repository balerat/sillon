from pathlib import Path
from typing import Optional

from silloncore.project_paths import resolve_storage_root, resolve_engine
from silloncore.engine import (
    get_project_context,
    get_run_details,
    add_metadata_to_runs,
    query_runs,
    delete_run as engine_delete_run,
    compare as engine_compare,
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

    # ---------------------------------------------------------
    # Run access
    # ---------------------------------------------------------

    def context(self, *run_names: str) -> dict:
        """Fetches the context summary of the project or of specific runs.

        Args:
            *run_names (str): Optional run names to target. If omitted, the
                project-wide overview is returned.

        Returns:
            dict: The engine context payload (`mode` and `runs` keys).
        """
        return get_project_context(self.engine, list(run_names) or None)

    def show(self, *run_names: str) -> None:
        """Pretty-prints the project context, like `sillon context` does.

        With no argument, an overview table of all runs is displayed. With
        run names, a detail card is displayed for each targeted run. Works
        in a terminal and in a jupyter notebook.

        Args:
            *run_names (str): Optional run names to target.
        """
        print_context(self.context(*run_names), project_name=self.path.name)

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
            has_parameter / has_metadata / has_result / has_analysis /
                has_artifact (str | list, optional): Name(s) that must exist.
            has_tag / tags (str | list, optional): Tag(s) the run must have.
            parameters / metadata / results / analyses (dict, optional):
                Value/predicate conditions on that dimension.
            fields (dict, optional): Conditions on top-level columns (e.g.
                `{"status": "SUCCESS", "author": "doph"}`).
            before / after (datetime | str, optional): Run-date bounds.
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

    def details(
        self,
        run_names=None,
        parameters=None,
        metadata=None,
        results=None,
    ) -> dict:
        """Queries run details exactly like `sillon show` does.

        Each category accepts a list of keys, a single key, or True to fetch
        everything in that category.

        Args:
            run_names (str | list, optional): Run name(s) to target.
            parameters (str | list | bool, optional): Parameter keys to fetch.
            metadata (str | list | bool, optional): Metadata keys to fetch.
            results (str | list | bool, optional): Result keys to fetch.

        Returns:
            dict: The engine payload with `parameter`, `metadata`, `result`
                and `artifacts` keys, present only if requested.
        """
        wildcard = ["%all%"]
        return get_run_details(
            self.engine,
            run_names=_as_list(run_names) or [],
            params=wildcard if parameters is True else _as_list(parameters),
            meta=wildcard if metadata is True else _as_list(metadata),
            results=wildcard if results is True else _as_list(results),
        )

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

    def compare(self, run_name1: str, run_name2: str) -> dict:
        """Diffs two runs (parameters, context, source), like `sillon compare`.

        Args:
            run_name1 (str): The baseline run name.
            run_name2 (str): The target run name.

        Returns:
            dict: The engine diff payload (`diff_param`, `diff_status`,
                `diff_runtime`, `diff_source`).
        """
        return engine_compare(self.engine, run_name1, run_name2)

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
        return f"Project({self.path.name} @ {self.path})"


def load_project(project_path=None) -> Project:
    """Loads a sillon project from a path (defaults to the current directory).

    Args:
        project_path (str | Path, optional): The project root containing the
            `.sillon` directory.

    Returns:
        Project: The loaded project.
    """
    return Project(project_path)
