# Architecture

sillon is a monorepo that builds as one distribution but is organized into five import packages:

| Package | Role |
|---|---|
| `silloncommon` | Data layer: SQLModel ORM (`SimulationTable`, `ArtifactTable`, `FigureTable`, `AnalysisTable`), the queries, and the JSON-RPC command protocol shared by client and server. |
| `silloncore` | The **engine** (the single source of truth for all read/query/export logic), the logging **server**, HDF5 **glob** storage, and the `.sillon` environment handler. |
| `sillonpy` | The Python client used inside simulation scripts (the `Tracker` + the user-facing API). |
| `silloncli` | The `sillon` command-line tool. |
| `sillonlab` | The analysis library for scripts and notebooks. |

## How a run is logged

```
your script ──sillonpy──▶ background server ──▶ SQLite (.sillon/database.sql)
   (Tracker)   JSON-RPC      (silloncore)    └─▶ HDF5 globs + artifacts/figures
```

1. `sp.init(...)` creates a `Tracker`, which ensures the **server daemon** is running (spawned via
   the current interpreter) and registers the run (the server assigns a unique, auto-incremented
   name).
2. Each `log_*` / `add_*` call is sent to the server as a JSON-RPC **command**
   (`silloncommon.commands`), dispatched through a visitor onto the in-memory `Simulation` object.
3. Lightweight values live inline in the database; large arrays are staged and written to the
   run's **HDF5 glob**; files become **artifacts**; matplotlib figures become **figures** (with
   `used=` provenance).
4. On exit (or `force_dump()`), the server finalizes runtime/status, commits the source into the
   glob, and inserts the row(s) into SQLite.

## Client/server transport

Client and daemon exchange length-prefixed JSON-RPC frames over a connected stream socket.
*Which* kind of socket is the only platform-dependent part of the system, and it is confined to
`silloncommon.transport`:

| Transport | Endpoint | Used when |
|---|---|---|
| `unix` | `AF_UNIX` socket at `.sillon/daemon.sock` | `socket.AF_UNIX` exists (Linux, macOS) |
| `tcp` | `AF_INET` on `127.0.0.1`, ephemeral port published in `.sillon/daemon.port` | it does not (Windows) |

Selection is by capability (`hasattr(socket, "AF_UNIX")`) rather than by `sys.platform`. CPython
does not expose `AF_UNIX` on Windows in any released version — [cpython#77589][afunix] is still
open — but the day it does, Windows picks up Unix sockets with no code change.

Set `SILLON_TRANSPORT=unix|tcp` to force one. That is how the Windows path gets tested on POSIX
CI; see the `test-tcp-transport` job.

A loopback TCP port is reachable by any local process, so the daemon writes a random secret to
`.sillon/daemon.token` (mode `0600` where that means anything) and every client must present it in
its REGISTER frame — the first frame on every connection. Commands sent on a connection that has
not successfully registered are refused. The check runs on both transports.

[afunix]: https://github.com/python/cpython/issues/77589

## Storage layout

```
.sillon/
  config.toml            # project id + storage root
  database.sql           # SQLite: one row per run + linked artifact/figure/analysis rows
  glob/<uuid>/glob.hdf5  # heavy results, big-array params, analyses, source
  artifact/<uuid>/...    # copied result files
  figure/<uuid>/...      # logged figures
  daemon.sock            # AF_UNIX endpoint  (unix transport)
  daemon.port            # listening port    (tcp transport)
  daemon.token           # REGISTER secret
  daemon.pid / .lock     # liveness + spawn serialization
```

## Reading and querying (the engine)

Both the CLI and `sillonlab` go through `silloncore.engine` — they never touch the database or
globs directly. Key entry points: `get_run_snapshot`, `load_run_result` / `load_run_parameter` /
`load_run_analysis`, `export_run` / `export_run_report`, `prune_runs` / `delete_run`, and
`query_runs`.

### Two-phase queries

`query_runs` is deliberately split so glob reads stay rare:

- **Cheap phase** — a single bulk `select_run_index` fetch is filtered in memory on everything
  that lives in the database (parameters, metadata, tags, date, columns via `match_cheap`, and all
  `has_*` presence checks). No HDF5 files are opened.
- **Heavy phase** — only the survivors with result/analysis *value* conditions have their glob
  opened (once per run, via `read_glob_many`) to evaluate `match_heavy`.

New searchable scalar fields (e.g. a future git hash) are added in one place,
`engine._searchable_columns`, which flattens the `hashes` column — no query rewrite needed.
