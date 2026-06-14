import uuid
from pathlib import Path

import h5py
import numpy as np 

ARRAY_SIZE_THRESHOLD = 1024 * 10 # 10KB - below this, send inline

def is_large_array(value) -> bool:
    return isinstance(value, np.ndarray) and value.nbytes > ARRAY_SIZE_THRESHOLD

def write_staging_array(value: np.ndarray, project_path: Path) -> dict:
    """Write array to a staging HDF5 file, return a pointer dict."""
    staging_dir = project_path / ".sillon" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    staging_path = staging_dir / f"{uuid.uuid4().hex}.h5"
    hdf5_key = "data" 
    with h5py.File(staging_path, "w") as f:
        f.create_dataset(hdf5_key, data=value)

    return {
            "__sillon_array_ref__": True,
            "staging_path": str(staging_path),
            "hdf5_key": hdf5_key,
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "nbytes": value.nbytes
            }



