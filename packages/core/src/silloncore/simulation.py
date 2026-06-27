from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from names_generator import generate_name

from .envhandler import RunEnvironmentHandler
from .glob import get_hash


@dataclass
class ResultItem:
    """A standardized data structure representing the result of a simulation.

    Attributes:
        value (Any): The actual result value, or a pointer/path to the result.
        is_artifact (bool): Indicates if the result is a saved physical file (artifact). Defaults to False.
        hsh (str): The SHA-256 hash of the result or artifact for integrity tracking. Defaults to "".
    """
    value: Any
    is_artifact: bool = False
    hsh: str = ""


@dataclass
class FigureItem:
    """A standardized data structure representing a figure logged during a run.

    Attributes:
        value (str): The storage pointer of the saved figure file.
        hsh (str): The SHA-256 hash of the figure file.
        meta (dict): Provenance metadata: which parameters/results were used
            to draw the figure (`used` key), a caption, the file format...
    """
    value: str
    hsh: str = ""
    meta: Dict[str, Any] = None


@dataclass
class SimHashes:
    """Stores hashes related to various components of a simulation run.

    Attributes:
        source (str): Hash of the main script source code. Defaults to "".
        git (str): Hash representing the current Git commit state. Defaults to "".
        project (str): Hash representing the project state. Defaults to "".
        parameters (str): Hash of the input parameters. Defaults to "".
        artifacts (str): Hash of the saved artifacts. Defaults to "".
        result_out (str): Hash of the standard output or result stream. Defaults to "".
    """
    source: str = ""
    git: str = ""
    project: str = ""
    parameters: str = ""
    artifacts: str = ""
    result_out: str = ""


# Functions to process special types of metadata without bloating add_metadata

def commit_source(simulation_obj, source):
    """Commits the main script source to the simulation's HDF5 glob and hashes it.

    Args:
        simulation_obj (Simulation): The active simulation instance.
        source (str): The raw source code string to be saved.
    """
    simulation_obj.hashes.source = get_hash(source)
    simulation_obj.glob.commit_source(source)


def commit_runtime(simulation_obj, runtime):
    """Commits the runtime duration to the simulation object.

    Args:
        simulation_obj (Simulation): The active simulation instance.
        runtime (str | float): The calculated execution time of the run.
    """
    simulation_obj.runtime = runtime


def commit_status(simulation_obj, status):
    """Commits the execution status to the simulation object.

    Args:
        simulation_obj (Simulation): The active simulation instance.
        status (str): The current status (e.g., "SUCCESS", "FAILED").
    """
    simulation_obj.status = status


# A lookup table to process sillon custom metadata when it arrives.
METADATA_TABLE = {
    "sillon.main_script_source": commit_source,
    "sillon.runtime": commit_runtime,
    "sillon.status": commit_status,
    # "sillon.isdirty": commit_isdirty,
}


class SingletonMeta(type):
    """A metaclass that implements the Singleton design pattern.

    Ensures that only one instance of any class using this metaclass is ever created.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance

        return cls._instances[cls]


class SimulationDict(metaclass=SingletonMeta):
    """A centralized registry to hold all active simulations.

    All simulations are represented through a dictionary. To ensure the uniqueness 
    of this registry across the application, it utilizes the Singleton pattern.

    Attributes:
        sim_dict (dict): The internal dictionary storing `Simulation` objects by their `run_id`.
    """

    def __init__(self):
        """Initializes the SimulationDict with an empty internal dictionary."""
        self.sim_dict = {}

    def add_sim(self, run_id, **kwargs):
        """Adds a simulation to the registry.

        Each simulation is characterized by a unique key (`run_id`). 
        Once added, the simulations can be manipulated individually.

        Args:
            run_id (str): The unique identifier for the simulation run.
            **kwargs: Keyword arguments passed directly to the `Simulation` constructor.
        """
        self.sim_dict[run_id] = Simulation(run_id, **kwargs)

    def rm_sim(self, key):
        """Removes a simulation from the registry based on its unique identifier.

        Args:
            key (str): The `run_id` of the simulation to remove.
        """
        self.sim_dict.pop(key)


####################################################################################
# Definition of the singleton "simulation" object                                  #
# Once this file is imported, one can use this object to manipulate the simulation #
# The singleton ensures that this is the only definition of the simulation         #
####################################################################################

Simulations_object = (
    SimulationDict()
)  # TODO : remove this instanciation ? Since it is now in the common features...


class Simulation:
    """Represents a single, trackable simulation run.

    Handles the collection of parameters, results, metadata, tags, and notes,
    as well as managing the underlying environment storage (artifacts and HDF5 glob).

    Attributes:
        run_id (str): The unique identifier (UUID) for the run.
        run_name (str): The human-readable name of the run.
        envh (RunEnvironmentHandler): Handler for artifacts and glob files.
        glob (Glob): The HDF5 interface for heavy data storage.
        platform (str): Operating system or platform executing the run.
        project_name (str): The name of the parent project.
        hostname (str): The machine's hostname.
        organisation (str): The organization running the project.
        author (str): The user executing the run.
        runtime (str): The execution duration of the run.
        status (str): Current execution status (e.g., 'RUNNING').
        parameters (Dict[str, Any]): Tracked input parameters.
        results (Dict[str, ResultItem]): Tracked output metrics and artifacts.
        metadata (Dict[str, Any]): Custom tracked metadata.
        tags (list): User-defined tags.
        notes (list): User-defined textual notes.
        hashes (SimHashes): Object tracking hashes of various components.
        date (str): Timestamp string of when the run was created.
    """

    def __init__(self, run_id, run_name, project_name, platform, hostname, organisation, author, project_path):
        """Initializes the Simulation object and its underlying storage environment.

        Args:
            run_id (str): The unique UUID for this specific run.
            run_name (str): The specific name given to this run (auto-generated if empty).
            project_name (str): Name of the parent project.
            platform (str): Execution platform/OS details.
            hostname (str): The local hostname.
            organisation (str): The organization managing the run.
            author (str): The author/creator of the run.
            project_path (str | Path): The base directory of the active project.
        """
        self.run_id = run_id
        self.run_name = run_name
        self.envh = RunEnvironmentHandler(run_id, project_path)
        self.glob = self.envh.create_glob()
        self.platform = platform
        self.project_name = project_name
        self.hostname = hostname
        self.organisation = organisation
        self.author = author

        self.runtime = ""
        self.status = "RUNNING"

        self.parameters: Dict[str, Any] = {}
        self.results: Dict[str, ResultItem] = {}
        self.figures: Dict[str, FigureItem] = {}
        self.metadata: Dict[str, Any] = {}
        self.tags = []
        self.notes = []
        self.hashes = SimHashes()
        
        self.check_name()
        self.set_date()

    def check_name(self):
        """Verifies the run name exists, generating a random one if it is empty or None."""
        if self.run_name == "" or self.run_name is None:
            self.run_name = generate_name() 

    def set_date(self):
        """Sets the creation date of the run based on the current system time."""
        self.date = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

    # ---------------------------------------------------------
    # Saving functions
    # ---------------------------------------------------------

    def log_param(self, name: str, value: Any):
        """Logs a parameter key-value pair to the simulation state.

        Lightweight, JSON-serializable values are stored inline in the
        database. Heavy parameter arrays arrive as a staging reference
        (``__sillon_array_ref__``) and are offloaded to the run's HDF5 glob
        ``parameter`` group, exactly like large results; the database then
        only keeps a small marker recording the pointer, shape and dtype.

        Args:
            name (str): The name of the parameter.
            value (Any): The value of the parameter, or a staging reference.
        """
        # TODO: Add overwrite check if needed
        if isinstance(value, dict) and value.get("__sillon_array_ref__"):
            staging_path = Path(value["staging_path"])
            pointer, hsh = self.glob.save_param_from_staging(name, staging_path)
            self.parameters[name] = {
                "__sillon_array_ref__": True,
                "pointer": pointer,
                "shape": value.get("shape"),
                "dtype": value.get("dtype"),
            }
        else:
            self.parameters[name] = value

    def add_metadata(self, name: str, value: Any):
        """Adds custom metadata to the simulation.

        Checks the `METADATA_TABLE` to see if the metadata key requires special 
        handling (e.g., source code). Otherwise, saves it standardly.

        Args:
            name (str): The metadata key or reserved namespace key.
            value (Any): The metadata value or payload.
        """
        special_handler = METADATA_TABLE.get(name)

        if special_handler:
            special_handler(self, value)
        else:
            self.metadata[name] = value

    def add_note(self, name: str, value: Any):
        """Appends a textual note to the simulation run.

        Args:
            name (str): Unused mapping key (kept for API consistency).
            value (Any): The note content.
        """
        self.notes.append(value)

    def add_tag(self, name: str, value: Any):
        """Appends a tag string to the simulation run.

        Args:
            name (str): Unused mapping key (kept for API consistency).
            value (Any): The tag string.
        """
        self.tags.append(value)

    def log_result(self, name, value_dict):
        """Saves a metric, dataset, or file artifact as a result.

        This command handles multiple data flows:
        1. Simple data logging (saves to HDF5 glob).
        2. File artifact copying (copies a file and logs its DB pointer).
        3. Simple DB logging without copying the artifact (if `save_result` is False).

        Args:
            name (str): The identifier name for the result.
            value_dict (dict): A dictionary containing routing instructions.
                Expected keys include:
                - `value` (Any): The actual data to save into HDF5.
                - `path` (str): The file path if logging an external artifact.
                - `save_result` (bool): Whether to physically copy the artifact into 
                  the project directory (Defaults to False).

        Note:
            You cannot provide `path=None` and `save_result=False` at the same time.
            This function currently relies on a globally defined environment handler 
            and requires further testing for massive data dumps.
        """
        data = value_dict.get("value")
        path = value_dict.get("path")
        save_result = value_dict.get(
            "save_result", False
        )  # defaults to False if missing
        
        if path is not None:
            if save_result is True:
                pointer, hsh = self.envh.save_artifact(path)
                self.results[name] = ResultItem(pointer, is_artifact=True, hsh=hsh)
            else:
                hsh = get_hash(path)
                self.results[name] = ResultItem(path, hsh=hsh)

        # Treat large array case:
        elif isinstance(data, dict) and data.get("__sillon_array_ref__"):
            staging_path = Path(data["staging_path"])
            pointer, hsh = self.glob.save_from_staging(name, staging_path)
            self.results[name] = ResultItem(pointer, hsh=hsh)
                
        elif data is not None:
            pointer, hsh = self.glob.save(name, data)
            self.results[name] = ResultItem(pointer, hsh=hsh)

    def log_figure(self, name, value_dict):
        """Saves a tracked figure file with its provenance metadata.

        The figure file (already rendered by the client, e.g. a matplotlib
        png) is copied into the run's figure storage, hashed, and kept with
        its metadata so the database can record which data produced it.

        Args:
            name (str): The identifier name for the figure.
            value_dict (dict): A dictionary containing routing instructions.
                Expected keys:
                - `path` (str): The path of the rendered figure file.
                - `meta` (dict): Provenance metadata (`used` data names,
                  caption, format...).
                - `cleanup` (bool): Whether the source file is a temporary
                  staging file to delete after the copy (Defaults to False).
        """
        path = value_dict.get("path")
        meta = value_dict.get("meta") or {}
        cleanup = value_dict.get("cleanup", False)

        pointer, hsh = self.envh.save_figure(path)
        self.figures[name] = FigureItem(pointer, hsh=hsh, meta=meta)

        if cleanup:
            Path(path).unlink(missing_ok=True)

    # ---------------------------------------------------------
    # Loading functions
    # ---------------------------------------------------------

    def _get_item(self, name, sim_dict):
        """Internal helper to safely retrieve an item from a tracking dictionary.

        Args:
            name (str): The key to look up.
            sim_dict (dict): The target dictionary (parameters, results, etc.).

        Raises:
            KeyError: If the requested key does not exist.

        Returns:
            Any: The value stored at the key.
        """
        if name not in sim_dict:
            raise KeyError(f"Item '{name}' not found.")
        return sim_dict[name]

    def get_param(self, name):
        """Retrieves a tracked parameter by name.

        Args:
            name (str): The name of the parameter.

        Returns:
            Any: The stored parameter value.
        """
        return self._get_item(name, self.parameters)

    def get_result(self, name):
        """Retrieves a tracked result object by name.

        Args:
            name (str): The name of the result.

        Returns:
            ResultItem: The standard ResultItem object.
        """
        return self._get_item(name, self.results)

    def get_metadata(self, name):
        """Retrieves tracked metadata by name.

        Args:
            name (str): The key for the metadata.

        Returns:
            Any: The stored metadata payload.
        """
        return self._get_item(name, self.metadata)
