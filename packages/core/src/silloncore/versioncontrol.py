from difflib import unified_diff

from silloncommon.database import select_snapshot_name
from silloncore.glob import read_data


class Reference:
    """Represents a loaded snapshot of a simulation run from the database.

    This class facilitates quick lookups of a run's main elements without 
    having to query the database multiple times. It fetches core data, 
    artifacts, and the source code from the HDF5 glob.

    Attributes:
        name (str): The specific name of the run.
        date (str): The timestamp of the run.
        parameters (dict): The tracked input parameters.
        results (dict): The tracked output results and metrics.
        metadata (dict): Custom tracking metadata.
        id (str): The UUID of the run.
        runtime (str | float): The execution duration of the run.
        status (str): The final execution status of the run.
        artifacts (Any): Artifacts associated with the run, if any.
        source (str): The raw main script source code fetched from the glob.
    """

    def __init__(
        self, engine, uuid: str = None, run_name: str = None) -> None:
        """Initializes the Reference by fetching run data from the database.

        Note:
            Currently, the reference is initiated only by `run_name`. Future 
            implementations should prioritize `uuid` to handle the case of 
            duplicate run names securely.

        Args:
            engine (Engine): The active SQLAlchemy database engine.
            uuid (str, optional): The unique identifier of the run. Defaults to None.
            run_name (str, optional): The name of the run to query. Defaults to None.

        Raises:
            ValueError: If the database query encounters an error or fails.
        """
        # TODO: Make an easier search than by giving the full date (Like partial date for example).
        try:
            run_data_db, run_artifact_db = select_snapshot_name(
                engine, run_name
            )
        except:
            raise ValueError("[REFERENCE] : Wrong db query")

        if run_data_db == None:
            print("[REFERENCE]: Empty reference after db query")
            
        (
            self.name,
            self.date,
            self.parameters,
            self.results,
            self.metadata,
            self.id,
            self.runtime,
            self.status,
        ) = run_data_db[0]
        self.artifacts = run_artifact_db[0] if run_artifact_db != [] else None

        self.source = read_data(str(self.id), "metadata", "main_source")


class Diffref:
    """Diffing engine based on built-in difflib to differentiate two run references.

    This class extracts and compares the source code, parameters, and 
    execution context between two loaded `Reference` objects.

    Attributes:
        ref1 (Reference): The base/original simulation reference.
        ref2 (Reference): The target/new simulation reference.
        diff_source (str): The unified text diff of the source code.
        diff_parameters (dict): A dictionary detailing added, removed, and changed parameters.
        diff_runtime (tuple | None): The before and after states of the runtime.
        diff_status (tuple | None): The before and after states of the status.
    """

    # TODO: Make it possible to compare a run and a list of runs or multiple runes specifically given.
    def __init__(self, ref1: Reference, ref2: Reference) -> None:
        """Initializes the diffing engine and computes all differences.

        Args:
            ref1 (Reference): The first simulation reference to act as the baseline.
            ref2 (Reference): The second simulation reference to compare against.
        """
        self.ref1 = ref1
        self.ref2 = ref2

        self.get_diff_source()
        self.get_diff_parameters()
        self.get_diff_context()

        # TODO: Add a diff for the result and artifact loading the glob

    def get_diff_source(self):
        """Computes the unified diff between the source codes of the two references.

        The resulting unified diff string is generated using `difflib` and 
        stored in the `diff_source` attribute.
        """
        source1 = self.ref1.source.splitlines(keepends=True)
        source2 = self.ref2.source.splitlines(keepends=True)

        diff = unified_diff(
            source1,
            source2,
            fromfile=self.ref1.name + "/" + self.ref1.date,
            tofile=self.ref2.name + "/" + self.ref2.date,
        )

        self.diff_source = "".join(diff)

    def get_diff_parameters(self):
        """Computes the set differences between the parameters of both references.

        Identifies newly added keys, removed keys, and keys whose values have changed.
        The results are stored in the `diff_parameters` attribute formatted as 
        a dictionary containing `diff_data`, `diff_key_added`, and `diff_key_removed`.
        """
        keys1 = set(self.ref1.parameters.keys())
        keys2 = set(self.ref2.parameters.keys())

        added = keys2 - keys1
        removed = keys1 - keys2
        common = keys1 & keys2

        # In the format {"changed_key": [old_value, new_value, percent(if not a str)]}
        diff_data = {}
        for key in common:
            value_old = self.ref1.parameters[key]
            value_new = self.ref2.parameters[key]
            diff_data[key] = simple_compare(value_old, value_new)

        self.diff_parameters = {
            "diff_data": diff_data,
            "diff_key_added": added,
            "diff_key_removed": removed,
        }

    def get_diff_context(self):
        """Computes the differences for basic metadata and execution context.

        Calculates the differences between the `runtime` and `status` of the 
        two references and stores them in their respective class attributes.
        """
        # TODO: Take into account more differences of basic metadata or run parameters
        self.diff_runtime = simple_compare(self.ref1.runtime, self.ref2.runtime)
        self.diff_status = simple_compare(self.ref1.status, self.ref2.status)


def simple_compare(value_old, value_new):
    """Compares two generic values to format their differences.

    Args:
        value_old (Any): The original tracking value.
        value_new (Any): The new tracking value.

    Returns:
        tuple | None: Returns `None` if the values are identical. Otherwise, 
            returns a tuple containing `(value_old, value_new, "N/A")`.
    """
    if value_old == value_new:
        return None
    
    return (value_old, value_new, "N/A")
