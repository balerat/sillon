import json
import numpy as np
from pathlib import Path

"""
Handles JSON-RPC encoding and decoding for the Sillon protocol.
Includes a custom encoder for NumPy and Python scientific types,
and a decode hook to reconstruct special types on the way back.
"""


def _decode_hook(obj: dict):
    """Reconstructs special types that were encoded by NumpyEncoder.
    Currently handles complex numbers stored as {'__complex__': True, 'real': ..., 'imag': ...}
    """
    if obj.get("__complex__"):
        return complex(obj["real"], obj["imag"])
    return obj


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles NumPy and Python scientific types.
    Raises TypeError for unknown custom objects rather than silently
    producing useless output."""

    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.complexfloating):
            # Cast real/imag to float explicitly to avoid re-entering the encoder
            return {"__complex__": True, "real": float(obj.real), "imag": float(obj.imag)}
        if isinstance(obj, complex):
            return {"__complex__": True, "real": obj.real, "imag": obj.imag}
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(
            f"Object of type {type(obj).__name__} is not JSON serializable. "
            f"Convert it to a dict, list, or string before logging."
        )


class RPCHandler:
    def __init__(self):
        self.JSONRPC_VERSION = "2.0"

    def decode_request(self, request: str) -> dict:
        """Decodes the outer JSON-RPC envelope. Does not decode params —
        that is done in _dispatch where the decode hook can be applied."""
        return json.loads(request)

    def decode_params(self, params: str) -> dict:
        """Decodes the params payload, reconstructing special types
        such as complex numbers encoded by NumpyEncoder."""
        return json.loads(params, object_hook=_decode_hook)

    def decode_response(self, response: str) -> dict:
        """Decodes a JSON-RPC response. Raises if the response contains an error."""
        decoded = json.loads(response)
        if "error" in decoded:
            raise Exception(decoded["error"])
        return decoded

    def encode_request(self, command, command_id: int, run_id: str) -> str:
        """Encodes a command into a JSON-RPC request string.
        Uses NumpyEncoder to handle scientific types in the params payload."""
        return json.dumps(
            {
                "jsonrpc": self.JSONRPC_VERSION,
                "method": command.method,
                "params": json.dumps(
                    {"name": command.name, "value": command.value, "run_id": run_id},
                    cls=NumpyEncoder,
                ),
                "id": command_id,
            }
        )

    def encode_response(self, response, id: int, error: str = "") -> str:
        """Encodes a result or error into a JSON-RPC response string."""
        if error == "":
            return json.dumps(
                {"jsonrpc": self.JSONRPC_VERSION, "result": response, "id": id}
            )
        else:
            return json.dumps(
                {
                    "jsonrpc": self.JSONRPC_VERSION,
                    "result": response,
                    "error": error,
                    "id": id,
                }
            )
