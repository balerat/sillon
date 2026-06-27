from pathlib import Path
from typing import Any, List, Optional

from silloncore.engine import (
    get_run_snapshot,
    load_run_result,
    load_run_parameter,
    load_run_artifact,
    load_run_source,
    load_run_figure,
    load_run_analysis,
    add_run_analysis,
    add_metadata_to_runs,
    delete_run as _engine_delete_run,
    fetch_run_result,
    get_run_sizes,
    export_run,
    build_run_report,
    export_run_report,
)

from sillonlab.display import print_run, print_run_table


class Run:
    """A lazy handle on a single logged simulation run.

    The object is cheap to create: it only holds the run name and the project
    pointers. All the data is fetched through the silloncore engine on first
    access and cached, so a notebook can hold hundreds of handles for free.

    Attributes:
        name (str): The human-readable name of the run.
        uuid (str): The unique identifier of the run (available after the
            first data access).
        timestamp (str): The creation date of the run.
        status (str): The final execution status of the run.
    """

    def __init__(self, name: str, engine, storage_root: Path, context: dict = None) -> None:
        """Initializes the run handle.

        Args:
            name (str): The run name (or uuid) used to query the engine.
            engine (Engine): The active SQLAlchemy engine of the project.
            storage_root (Path): The root folder holding the `glob` and
                `artifact` directories of the project.
            context (dict, optional): A summary dictionary as returned by
                `silloncore.engine.get_project_context` to pre-fill the
                lightweight fields. Defaults to None.
        """
        self.name = name
        self.engine = engine
        self.storage_root = Path(storage_root)

        context = context or {}
        self.uuid = None
        self.timestamp = context.get("timestamp")
        self.status = context.get("status")

        self._snapshot = None

    # ---------------------------------------------------------
    # Internal loading helper
    # ---------------------------------------------------------

    def _load_snapshot(self) -> dict:
        """Fetches and caches the full run snapshot from the engine."""
        if self._snapshot is None:
            snapshot = get_run_snapshot(self.engine, self.name)
            if snapshot is None:
                raise LookupError(f"Run '{self.name}' not found in the project database.")
            self._snapshot = snapshot
            self.name = snapshot["name"]
            self.uuid = snapshot["uuid"]
            self.timestamp = snapshot["date"]
            self.status = snapshot["status"]
        return self._snapshot

    # ---------------------------------------------------------
    # Tracked data as properties
    # ---------------------------------------------------------

    @property
    def parameters(self) -> dict:
        """All logged parameters of the run as a dictionary."""
        return dict(self._load_snapshot()["parameters"])

    @property
    def results(self) -> List[str]:
        """The names of all logged results and artifacts of the run."""
        snapshot = self._load_snapshot()
        return list(snapshot["results"].keys()) + list(snapshot["artifacts"].keys())

    @property
    def metadata(self) -> dict:
        """All logged metadata of the run as a dictionary."""
        return dict(self._load_snapshot()["meta_data"])

    @property
    def tags(self) -> list:
        """The tags attached to the run."""
        return list(self._load_snapshot()["tag"] or [])

    @property
    def notes(self) -> list:
        """The notes attached to the run."""
        return list(self._load_snapshot()["note"] or [])

    @property
    def runtime(self) -> Optional[str]:
        """The execution duration of the run."""
        return self._load_snapshot()["runtime"]

    @property
    def figures(self) -> dict:
        """The figures logged during the run, with their provenance metadata.

        Each entry maps the figure name to its metadata: the `used` key lists
        the parameters/results the figure was built from.
        """
        return {
            name: dict(figure["meta"] or {})
            for name, figure in self._load_snapshot()["figures"].items()
        }

    @property
    def analyses(self) -> dict:
        """The post-processed analyses attached to the run, with their context."""
        return {
            name: dict(analysis["meta"] or {})
            for name, analysis in self._load_snapshot()["analyses"].items()
        }

    # ---------------------------------------------------------
    # Loading functions
    # ---------------------------------------------------------

    def _load_parameter(self, name: str) -> Any:
        # Heavy array parameters are read back from the glob; light ones come
        # straight from the database (engine handles both transparently).
        return load_run_parameter(self.storage_root, self._load_snapshot(), name)

    def _load_metadata(self, name: str) -> Any:
        snapshot = self._load_snapshot()
        if name not in snapshot["meta_data"]:
            raise LookupError(f"Invalid metadata '{name}' for run '{self.name}'.")
        return snapshot["meta_data"][name]

    @staticmethod
    def _load_many(loader, names: tuple, kind: str):
        if len(names) == 0:
            raise ValueError(f"Error loading {kind}: please provide a {kind} name.")
        if not all(isinstance(name, str) for name in names):
            raise ValueError(f"Error loading {kind}: names must be strings.")
        if len(names) == 1:
            return loader(names[0])
        return [loader(name) for name in names]

    def load_parameter(self, *names: str) -> Any:
        """Loads one or more parameter values by name.

        Args:
            *names (str): The parameter name(s) to load.

        Returns:
            Any: The value if one name is given, otherwise a list of values.
        """
        return self._load_many(self._load_parameter, names, "parameter")

    def load_result(self, *names: str) -> Any:
        """Loads one or more results by name, through the engine.

        Heavy results saved to the HDF5 glob are read back from disk. Results
        logged as artifacts return the path to the stored copy. Plain values
        or external paths are returned as stored in the database.

        Args:
            *names (str): The result name(s) to load.

        Returns:
            Any: The value if one name is given, otherwise a list of values.
        """
        snapshot = self._load_snapshot()
        return self._load_many(
            lambda name: load_run_result(self.storage_root, snapshot, name),
            names,
            "result",
        )

    def load_metadata(self, *names: str) -> Any:
        """Loads one or more metadata values by name, or all of them.

        Args:
            *names (str): The metadata name(s) to load. If omitted, the whole
                metadata dictionary is returned.

        Returns:
            Any: The full dictionary, a single value, or a list of values.
        """
        if len(names) == 0:
            return self.metadata
        return self._load_many(self._load_metadata, names, "metadata")

    def load_artifact(self, name: str) -> Path:
        """Resolves the on-disk location of a saved artifact.

        Args:
            name (str): The result name the artifact was logged under.

        Returns:
            Path: The path to the artifact file, or to its folder if the
                artifact holds several files.
        """
        return load_run_artifact(self.storage_root, self._load_snapshot(), name)

    def load_source(self) -> Optional[str]:
        """Loads the main script source code recorded for the run."""
        return load_run_source(self.storage_root, self._load_snapshot())

    def load_figure(self, name: str) -> Path:
        """Resolves the on-disk location of a figure logged during the run.

        Args:
            name (str): The name the figure was logged under.

        Returns:
            Path: The path to the figure file (e.g., to open or display in
                a notebook with `IPython.display.Image`).
        """
        return load_run_figure(self.storage_root, self._load_snapshot(), name)

    def fetch_result(self, name: str, dest=None) -> Path:
        """Fetches a result, artifact, or figure as a file on disk.

        Artifacts and figures are copied as-is; glob results are saved as
        `.npy` (or `.txt` for strings). Use `load_result` instead to get the
        value directly in memory.

        Args:
            name (str): The result, artifact, or figure name to fetch.
            dest (str | Path, optional): The destination directory. Defaults
                to the current working directory.

        Returns:
            Path: The path of the fetched copy.
        """
        return fetch_run_result(self.storage_root, self._load_snapshot(), name, dest)

    def sizes(self) -> dict:
        """Measures the storage footprint of every stored item of the run.

        Returns:
            dict: Mapping of item names to `{"kind": str, "bytes": int}`.
        """
        return get_run_sizes(self.storage_root, self._load_snapshot())

    def export(self, dest=None, format: str = "npz") -> dict:
        """Exports the stored data of the run into a portable file.

        Args:
            dest (str | Path, optional): Output file (or folder for "npy").
                Defaults to `<run_name>_export.<ext>` in the current directory.
            format (str): One of "npz", "npy", "hdf5". The hdf5 export also
                embeds the parameters and run identity. Defaults to "npz".

        Returns:
            dict: `{"path": Path, "exported": [names], "skipped": [names]}`.
        """
        return export_run(self.storage_root, self._load_snapshot(), dest, format)

    def report(self, dest=None, with_data: bool = False) -> Path:
        """Exports a self-contained context bundle (zip) describing the run.

        The bundle answers "what did this run use and do": a JSON manifest, a
        readable `report.md`, the recorded entry script, and optionally the
        run's data as HDF5. Ideal to archive a run or drop it in a thesis
        appendix.

        Args:
            dest (str | Path, optional): Output zip path. Defaults to
                `<run_name>_report.zip` in the current directory.
            with_data (bool): Also embed results/analyses as HDF5. Defaults
                to False.

        Returns:
            Path: The path of the written zip bundle.
        """
        return export_run_report(
            self.engine, self.storage_root, self._load_snapshot(), dest, with_data
        )

    def manifest(self) -> dict:
        """Returns the structured run report as a dictionary (no file written)."""
        return build_run_report(self.engine, self.storage_root, self._load_snapshot())

    # ---------------------------------------------------------
    # Annotation functions
    # ---------------------------------------------------------

    def _annotate(self, **kwargs) -> dict:
        out = add_metadata_to_runs(self.engine, [self.name], **kwargs)
        self._snapshot = None  # Invalidate the cache so new data is visible
        return out

    def add_note(self, note) -> dict:
        """Appends one or more notes to the run.

        Args:
            note (str | list): The note(s) to append.
        """
        return self._annotate(notes=[note] if isinstance(note, str) else list(note))

    def add_tag(self, tag) -> dict:
        """Appends one or more tags to the run.

        Args:
            tag (str | list): The tag(s) to append.
        """
        return self._annotate(tags=[tag] if isinstance(tag, str) else list(tag))

    def add_metadata(self, key_or_dict, value=None) -> dict:
        """Merges metadata into the run.

        Args:
            key_or_dict (str | dict): A metadata key, or a dictionary of
                metadata key/value pairs.
            value (Any, optional): The value when a single key is given.
        """
        if isinstance(key_or_dict, str):
            if value is None:
                raise ValueError(f"You provided a metadata key '{key_or_dict}' but no value.")
            metadata = {key_or_dict: value}
        else:
            metadata = dict(key_or_dict)
        return self._annotate(metadata=metadata)

    def add_analysis(self, name: str, data, **info) -> dict:
        """Attaches post-processed data to the run for later reuse.

        Use this when you derive new data from the run after the fact: for
        example, if the simulation fitted a function, store `f(x)` evaluated
        on your grid of interest and reload it later with `load_analysis`.

        Args:
            name (str): The analysis name.
            data (Any): The processed data to store (array-like).
            **info: Free-form context saved with the analysis (e.g.,
                `inputs=["coef"]`, `comment="evaluated on fine grid"`).

        Returns:
            dict: The stored analysis row (name, hash, date...).
        """
        row = add_run_analysis(
            self.engine, self.storage_root, self._load_snapshot(), name, data, info
        )
        self._snapshot = None  # Invalidate the cache so new data is visible
        return row

    def load_analysis(self, name: str) -> Any:
        """Loads back a post-processed analysis attached to the run.

        Args:
            name (str): The analysis name to load.

        Returns:
            Any: The stored analysis data.
        """
        return load_run_analysis(self.storage_root, self._load_snapshot(), name)

    # ---------------------------------------------------------
    # Analysis helpers
    # ---------------------------------------------------------

    def to_dataframe(self, metadata: bool = False, results: bool = False):
        """Builds a single-row pandas DataFrame of the run.

        Args:
            metadata (bool): If True, metadata keys are added as columns.
            results (bool): If True, results are loaded and added as columns.

        Returns:
            pandas.DataFrame: A one-row summary of the run.
        """
        return RunCollection([self]).to_dataframe(metadata=metadata, results=results)

    # ---------------------------------------------------------
    # Deletion
    # ---------------------------------------------------------

    def delete(self) -> dict:
        """Permanently deletes this run — its stored data and database row.

        This is irreversible: the run's glob, artifacts and figures are removed
        from disk and its database entry (with linked artifacts/figures/
        analyses) is dropped. After this call the handle is stale.

        Returns:
            dict: `{"status": "success", "deleted": str, "freed_bytes": int}`,
                or an error status if the run no longer exists.
        """
        out = _engine_delete_run(self.engine, self.storage_root, self.name)
        self._snapshot = None  # Invalidate the cache; the run is gone
        return out

    # ---------------------------------------------------------
    # Display
    # ---------------------------------------------------------

    def show(self) -> None:
        """Pretty-prints the run as a detail card (terminal or notebook)."""
        print_run(self)

    def __repr__(self):
        status = f" [{self.status}]" if self.status else ""
        return f"Run({self.name}{status})"


class RunCollection:
    """A list-like container of `Run` objects with analysis helpers."""

    def __init__(self, runs: List[Run]) -> None:
        self._runs = list(runs)

    def __len__(self):
        return len(self._runs)

    def __iter__(self):
        return iter(self._runs)

    def __getitem__(self, key):
        if isinstance(key, str):
            for run in self._runs:
                if run.name == key or run.uuid == key:
                    return run
            raise KeyError(f"No run named '{key}' in the collection.")
        if isinstance(key, slice):
            return RunCollection(self._runs[key])
        return self._runs[key]

    def __repr__(self):
        return f"RunCollection({[run.name for run in self._runs]})"

    def list(self) -> List[str]:
        """Returns the names of all runs in the collection."""
        return [run.name for run in self._runs]

    def filter(self, predicate) -> "RunCollection":
        """Returns a new collection of the runs matching the predicate.

        Args:
            predicate (Callable[[Run], bool]): A function tested on each run.
        """
        return RunCollection([run for run in self._runs if predicate(run)])

    def where(self, has_result=None, has_artifact=None, **conditions) -> "RunCollection":
        """Filters the collection on parameters, results, and artifacts.

        Parameter conditions map a name to a plain value (equality) or a
        callable predicate. `has_result` / `has_artifact` keep only runs that
        have the named result or artifact. All criteria must hold.

        Example:
            ```python
            runs.where(optimizer="adam", learning_rate=lambda v: v < 0.1)
            runs.where(has_result="coef")
            ```

        Args:
            has_result (str | list, optional): Result name(s) that must exist.
            has_artifact (str | list, optional): Artifact name(s) that must exist.
            **conditions: Parameter names mapped to values or predicates.

        Returns:
            RunCollection: The matching runs.
        """
        required_results = [has_result] if isinstance(has_result, str) else (has_result or [])
        required_artifacts = (
            [has_artifact] if isinstance(has_artifact, str) else (has_artifact or [])
        )

        def matches(run: Run) -> bool:
            parameters = run.parameters
            for key, condition in conditions.items():
                if key not in parameters:
                    return False
                if callable(condition):
                    if not condition(parameters[key]):
                        return False
                elif parameters[key] != condition:
                    return False

            results = set(run.results)
            if not all(name in results for name in required_results):
                return False

            artifact_names = run._load_snapshot()["artifacts"].keys()
            if not all(name in artifact_names for name in required_artifacts):
                return False

            return True

        return self.filter(matches)

    def show(self) -> None:
        """Pretty-prints the collection as a summary table."""
        print_run_table(self._runs)

    def to_dataframe(self, metadata: bool = False, results: bool = False):
        """Builds a pandas DataFrame summarizing the collection.

        Each row is a run with its name, timestamp, status, runtime and one
        column per logged parameter.

        Args:
            metadata (bool): If True, metadata keys are added as columns.
                Defaults to False.
            results (bool): If True, results are loaded (glob reads included)
                and added as columns. Defaults to False.

        Returns:
            pandas.DataFrame: The summary table, one row per run.
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "pandas is required for to_dataframe(): pip install pandas"
            ) from e

        rows = []
        for run in self._runs:
            row = {
                "name": run.name,
                "timestamp": run.timestamp,
                "status": run.status,
                "runtime": run.runtime,
            }
            row.update(run.parameters)
            if metadata:
                row.update(run.metadata)
            if results:
                for result_name in run.results:
                    row[result_name] = run.load_result(result_name)
            rows.append(row)

        return pd.DataFrame(rows)
