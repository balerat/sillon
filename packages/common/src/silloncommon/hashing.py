"""Content hashing, shared by the client and the daemon.

Lives in silloncommon so both sides compute hashes the *same* way. That matters
for large arrays: the client hashes them before staging (where the array
already sits in its memory) rather than making the daemon materialize the data
just to hash it. Two runs logging identical data must still produce identical
hashes whether the value travelled inline or through a staging file.
"""

import hashlib
import os
import pickle


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
