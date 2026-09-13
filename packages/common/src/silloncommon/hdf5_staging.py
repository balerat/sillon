import uuid
from pathlib import Path

import h5py
import json
import numpy as np

from silloncommon.hashing import get_hash
from numpy._core.numeric import ndarray 

ARRAY_SIZE_THRESHOLD = 1024 * 10 # 10KB - below this, send inline

def is_large_array(value, size_threshold=ARRAY_SIZE_THRESHOLD) -> bool:
    """Check if value is either too large or not JSON serializable."""
    
    # Whitelist of JSON-safe types
    json_safe_types = (type(None), bool, int, float, str)
    
    if isinstance(value, json_safe_types):
        return False
    
    # numpy arrays
    if isinstance(value, np.ndarray):
        return value.nbytes > size_threshold
    
    # Lists and dicts - try to serialize
    if isinstance(value, (list, dict, tuple)):
        try:
            size = len(json.dumps(value).encode('utf-8'))
            return size > size_threshold
        except TypeError:
            return True  # Has non-serializable content
    
    # Everything else (custom objects, functions, etc.)
    return True

def write_staging_array(value, project_path: Path) -> dict:
    """Write array to a staging HDF5 file, return a pointer dict."""
    staging_dir = project_path / ".sillon" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    staging_path = staging_dir / f"{uuid.uuid4().hex}.h5"
    hdf5_key = "data"
    with h5py.File(staging_path, "w") as f:
        f.create_dataset(hdf5_key, data=value)

    # Hashed here, not by the daemon. The array is already in this process's
    # memory, so hashing costs nothing extra -- whereas the daemon would have to
    # load the whole dataset back just to compute the same digest. Using the
    # shared get_hash keeps it identical to an inline-logged value.
    hsh = get_hash(value)
    
    if isinstance(value, ndarray):
        return {
                "__sillon_array_ref__": True,
                "staging_path": str(staging_path),
                "hdf5_key": hdf5_key,
                "hash": hsh,
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "nbytes": value.nbytes
                }
    else:
        return {
                "__sillon_array_ref__": True,
                "staging_path": str(staging_path),
                "hdf5_key": hdf5_key,
                "hash": hsh,
                }


