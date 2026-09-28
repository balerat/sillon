# silloncommon

The data layer and wire protocol, shared by the client and the daemon. Imports
nothing from the layers above it.

| Module | Role |
|---|---|
| `database.py` | SQLModel tables, queries, engine construction, schema migration |
| `commands.py`, `rpcHandler.py`, `framing.py` | the JSON-RPC command protocol |
| `transport.py`, `socket_path.py` | AF_UNIX / loopback-TCP transport |
| `hashing.py`, `codeversion.py`, `source_store.py` | content hashing and code versions |
| `hdf5_staging.py` | large-array handoff |
| `access_log.py` | which runs' data this process read, for automatic lineage |
| `registry.py`, `user_paths.py` | the machine-wide project registry |

Full documentation: [Architecture](../../docs/dev/architecture.md)
