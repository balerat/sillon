# Handle the saving of result in hdfs5 format and the hashing of result from the environment handler.
# The glob (hdfs5 file) is an object because it is treated as a special file with its own options

import h5py
import os
import pickle
import hashlib
from pathlib import Path


def get_hash(input_data):  # Don't work for directories for now
    """Generates a SHA-256 hash for a given file or Python object.

    If the input is a valid file path string, it hashes the file's contents. 
    Otherwise, it serializes the Python object using pickle and hashes the 
    resulting bytes. Note: This does not currently support hashing directories.

    Args:
        input_data (str | Any): A file path string or any picklable Python object.

    Returns:
        str: The hexadecimal SHA-256 hash string.
    """
    if isinstance(input_data, str) and os.path.isfile(input_data):
        with open(input_data, "rb") as f:
            digest = hashlib.file_digest(f, "sha256")
            return digest.hexdigest()
    else:
        data_bytes = pickle.dumps(input_data)
        sha256 = hashlib.sha256()
        sha256.update(data_bytes)
        return sha256.hexdigest()

def read_glob(storage_root, uuid, group, pointer):
    """Reads a dataset from a run's HDF5 glob file under a given storage root.

    Unlike `read_data`, this function does not rely on the current working
    directory: the caller provides the storage root holding the `glob` folder
    (usually the `.sillon` directory or the configured storage root).

    Args:
        storage_root (str | Path): The folder containing the `glob` directory.
        uuid (str): The unique identifier of the simulation run.
        group (str): The HDF5 group name (e.g., 'metadata' or 'result').
        pointer (str): The specific dataset name within the group.

    Returns:
        Any: The extracted data, decoded to a string if it was stored as
            bytes, or `None` if the glob file or the dataset does not exist.
    """
    g_path = Path(storage_root) / "glob" / str(uuid) / "glob.hdf5"
    if not g_path.exists():
        return None

    with h5py.File(str(g_path), "r") as g:
        dataset = f"{group}/{pointer}"
        if dataset not in g:
            return None
        data = g[dataset][()]
        return data.decode("utf-8") if isinstance(data, bytes) else data


def append_glob(storage_root, uuid, group, pointer, data):
    """Writes a dataset into a run's HDF5 glob after the run has ended.

    Used for post-hoc data (e.g., the `analysis` group): the glob file is
    reopened in append mode, the dataset is (over)written, and the data hash
    is returned for database tracking. The glob folder is created if the run
    never stored heavy data.

    Args:
        storage_root (str | Path): The folder containing the `glob` directory.
        uuid (str): The unique identifier of the simulation run.
        group (str): The HDF5 group name (e.g., 'analysis').
        pointer (str): The dataset name within the group.
        data (Any): The data to store (must be compatible with h5py).

    Returns:
        str: The SHA-256 hash of the stored data.
    """
    g_dir = Path(storage_root) / "glob" / str(uuid)
    os.makedirs(g_dir, exist_ok=True)

    with h5py.File(str(g_dir / "glob.hdf5"), "a") as g:
        target_group = g.require_group(group)
        if pointer in target_group:
            del target_group[pointer]
        target_group.create_dataset(pointer, data=data)
        g.flush()

    return get_hash(data)


def glob_sizes(storage_root, uuid, group="result"):
    """Lists the on-disk byte size of every dataset of a glob group.

    Args:
        storage_root (str | Path): The folder containing the `glob` directory.
        uuid (str): The unique identifier of the simulation run.
        group (str): The HDF5 group to inspect. Defaults to "result".

    Returns:
        dict: A mapping of dataset names to their size in bytes. Empty if the
            glob file or the group does not exist.
    """
    g_path = Path(storage_root) / "glob" / str(uuid) / "glob.hdf5"
    if not g_path.exists():
        return {}

    with h5py.File(str(g_path), "r") as g:
        if group not in g:
            return {}
        return {
            name: dataset.nbytes
            for name, dataset in g[group].items()
            if isinstance(dataset, h5py.Dataset)
        }


def read_data(uuid, group, pointer):
    """Retrieves specific data from a simulation's HDF5 glob file.

    This function accesses the HDF5 file for a specific run and extracts 
    the dataset located at the specified group and pointer. It assumes the 
    current working directory is the project root. Automatically decodes 
    byte strings to UTF-8.

    Args:
        uuid (str): The unique identifier of the simulation run.
        group (str): The HDF5 group name (e.g., 'metadata' or 'result').
        pointer (str): The specific dataset name within the group.

    Raises:
        FileNotFoundError: If the `glob.hdf5` file for the given UUID does not exist.
        KeyError: If the specified group/pointer path is not found in the file.

    Returns:
        Any: The extracted data, decoded to a string if it was stored as bytes, 
            or `None` if the operation fails gracefully.
    """
    cwd = Path(os.getcwd()).resolve()
    g_path = cwd / ".sillon" / "glob" / uuid / "glob.hdf5"
    if not g_path.exists():
        raise FileNotFoundError(f"[GLOB]: File not found at {str(g_path)}")

    with h5py.File(str(g_path), 'r') as g:
        dataset = f"{group}/{pointer}"
        if dataset not in g:
            raise KeyError(f'[GLOB]: wrong pointer to read glob at {g_path} for dataset: {dataset}')
        data = g[dataset][()]
        return data.decode('utf-8') if isinstance(data, bytes) else data

    return None

class Glob:
    """Manages the HDF5 storage backend (Glob) for a simulation run.

    This class handles creating, appending to, and closing the `glob.hdf5` 
    file for a specific run. It utilizes HDF5's SWMR (Single Writer Multiple 
    Reader) mode to allow the server to write data while external tools 
    simultaneously read it.

    Attributes:
        path (Path): The directory path where the `glob.hdf5` file is stored.
        file (h5py.File): The underlying HDF5 file object.
        results (list): A queue of tuples containing `(name, result_object)` 
            waiting to be committed to disk.
    """

    def __init__(self, simply_path: Path):
        """Initializes the Glob handler and opens the HDF5 file.

        Args:
            simply_path (Path): The directory path where the glob file should be created.
        """
        self.path = simply_path
        self.file = h5py.File(str(simply_path / "glob.hdf5"), "a", libver='latest')
        self.file.swmr_mode = True # Requires libver="latest" to be able to read the file while the server is running
        print(f"\n[SERVER] Creating/Writing to HDF5 at: {Path(str(simply_path / 'glob.hdf5')).resolve()}", flush=True)
        self.results = []
        self.parameters = []

    def save(self, name, result_object):
        """Queues a result to be saved and calculates its hash.

        Args:
            name (str): The target dataset name for this result.
            result_object (Any): The data to be saved (must be compatible with h5py).

        Returns:
            tuple: A tuple containing:
                - str: The name of the result.
                - str: The computed SHA-256 hash of the result object.
        """
        self.results.append((f"{name}", result_object))
        return name, get_hash(result_object)

    def save_from_staging(self, name:str, staging_path: Path):
        """Claims a pre-written staging hdf5 file by reading its dataset and writing it into the permanent glob, then deletes the staging file"""
        with h5py.File(staging_path, "r") as f:
            data = f["data"][()]
        pointer, hsh = self.save(name, data)
        staging_path.unlink(missing_ok=True)

        return pointer, hsh

    def save_param(self, name, param_object):
        """Queues a heavy parameter to be saved to the 'parameter' group.

        Mirrors `save` but targets the parameter group so large input arrays
        live in the glob (out of the SQLite database) exactly like results.

        Args:
            name (str): The target dataset name for this parameter.
            param_object (Any): The data to be saved (h5py-compatible).

        Returns:
            tuple: `(name, sha256_hash)`.
        """
        self.parameters.append((f"{name}", param_object))
        return name, get_hash(param_object)

    def save_param_from_staging(self, name: str, staging_path: Path):
        """Claims a staging hdf5 file into the permanent glob 'parameter' group, then deletes it."""
        with h5py.File(staging_path, "r") as f:
            data = f["data"][()]
        pointer, hsh = self.save_param(name, data)
        staging_path.unlink(missing_ok=True)

        return pointer, hsh


    def commit_result(self):
        """Writes all queued results to the HDF5 file on disk.

        Creates or requires the 'result' group and iterates through the `results` 
        queue to create datasets. If a dataset name already exists, it deletes 
        the old one to prevent errors before writing the new data. Forces a disk flush.
        """
        try:
            # Result are in the group "result" in the datasets
            # Let's assure it exists first
            res_group = self.file.require_group("result")

            for name, data in self.results:

                # If there is a duplicate we raise a warning and overwrite it with the last value (might need to change)
                if name in res_group:
                    print("Duplicate dataset")
                    del res_group[name]

                res_group.create_dataset(name, data=data)
            self.file.flush()  # Forces write to disk
        except TypeError as e:
            print(
                f"Failed to save data: {e}. Ensure 'data' is a NumPy array or compatible type."
            )

    def commit_parameter(self):
        """Writes all queued heavy parameters to the 'parameter' HDF5 group.

        Mirrors `commit_result`: requires the 'parameter' group, overwrites any
        duplicate dataset, and flushes to disk.
        """
        try:
            param_group = self.file.require_group("parameter")

            for name, data in self.parameters:
                if name in param_group:
                    print("Duplicate parameter dataset")
                    del param_group[name]

                param_group.create_dataset(name, data=data)
            self.file.flush()
        except TypeError as e:
            print(
                f"Failed to save parameter: {e}. Ensure 'data' is a NumPy array or compatible type."
            )

    def commit_source(self, source):
        """Saves the main source code string into the HDF5 metadata group.

        Args:
            source (str): The raw source code of the simulation script.
        """
        try:
            metadata_group = self.file.require_group("metadata")

            # To add: the sources of all the custom imports
            metadata_group.create_dataset("main_source", data=source) # use data to explictely make it work

            self.file.flush()

        except TypeError as e:
            print(
                f"Failed to save source: {e}. Ensure 'data' is a NumPy array or compatible type."
            )

    # TD CREATE SUBGROUP

    def close(self):
        """Safely closes the underlying HDF5 file."""
        self.file.close()
