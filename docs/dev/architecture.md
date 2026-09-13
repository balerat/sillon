# Architecture

sillon is one distribution built from five import packages.

| Package | Role |
|---|---|
| `silloncommon` | Data layer: the SQLModel ORM and queries, the JSON-RPC command protocol, hashing, staging, and the project registry. Imports nothing from the layers above. |
| `silloncore` | The **engine** (all read/query/export logic), the logging **daemon**, HDF5 **glob** storage, and the `.sillon` environment handler. |
| `sillonpy` | The client imported by simulation scripts. |
| `silloncli` | The `sillon` command-line tool. |
| `sillonlab` | The analysis library for scripts and notebooks. |

The layering matters: `silloncli` and `sillonlab` are thin renderers over
`silloncore.engine`, which returns plain dicts. That is why the CLI and the
notebook API never drift apart, and why a new output format is cheap to add.

## How a run is logged

```
your script ──sillonpy──▶ daemon ──▶ SQLite (.sillon/database.sql)
   (Tracker)   JSON-RPC   (silloncore)  └─▶ HDF5 globs + artifacts/figures
```

1. `sp.init(...)` or `sp.track_run(...)` creates a `Tracker`, which ensures the
   project's **daemon** is running (spawned with the current interpreter) and
   registers the run. The daemon assigns a unique name.
2. Each `log_*` / `add_*` call is sent as a JSON-RPC **command**
   (`silloncommon.commands`) and dispatched through a visitor onto the in-memory
   `Simulation` object.
3. Light values stay inline in the database. Large arrays are written by the
   *client* to a staging HDF5 file; the daemon claims them into the run's glob
   with an HDF5-level copy, so the data never passes through the daemon's
   memory. The client hashes them before staging, using the same `get_hash` as
   inline values, so digests remain comparable.
4. On exit (or `force_dump()`), the daemon finalises runtime and status, commits
   the source into the glob, and inserts the row into SQLite.

### Failure handling

- A command that fails server-side returns a top-level JSON-RPC `error`, which
  the client raises. Nothing is silently dropped.
- An uncaught exception in the script is caught by a chained `sys.excepthook`
  and the run is sealed `CRASHED`; the daemon only promotes a run to `SUCCESS`
  while its status is still `RUNNING`.
- A client that dies without dumping is detected by the dropped connection and
  its run is marked `CRASHED` from the daemon side.
- A failed commit rolls the shared session back, so one bad run cannot poison
  the ones after it.

## The daemon

One per project, keyed by the project path. Single-threaded, built on
`selectors`:

- Connections are registered **read-only**; write interest is added only when
  there is a reply to send. (Registering for write permanently makes an idle
  socket perpetually ready, which spins the loop and suppresses the idle check.)
- Idle shutdown after `SILLON_IDLE_TIMEOUT` seconds (default 300), and never
  while a run is still open.
- Framing is a 4-byte big-endian length prefix around UTF-8 JSON-RPC.

## Storage layout

```
.sillon/
  config.toml            project id + storage root
  database.sql           SQLite: one row per run + artifact/figure/analysis rows
  glob/<uuid>/glob.hdf5  heavy results, big-array params, analyses, source
  artifact/<uuid>/...    copied result files
  figure/<uuid>/...      logged figures
  staging/               short-lived handoff files for large arrays
  daemon.log / .pid / .sock / .lock
```

SQLite is opened in WAL mode with `busy_timeout` and `synchronous=NORMAL`, so
reading a project (a CLI command, a notebook) never blocks the daemon writing to
it. Indexes exist on `uuid`, `name`, `date`, `status` and the three `run_id`
foreign keys. Both are applied to existing databases on open, by `migrate_schema`.

## Reading and querying (the engine)

Both the CLI and `sillonlab` go through `silloncore.engine`; neither touches the
database or the globs directly. Key entry points: `get_run_snapshot`,
`load_run_result` / `load_run_parameter` / `load_run_analysis`, `export_run` /
`export_run_report`, `prune_runs` / `delete_run`, and `query_runs`.

### Two-phase queries

`query_runs` is split so glob reads stay rare:

- **Cheap phase** — one bulk `select_run_index` fetch, filtered in memory on
  everything that lives in the database (parameters, metadata, tags, dates,
  status, presence checks). No HDF5 file is opened.
- **Heavy phase** — only the survivors have their glob read, for value
  conditions on `results` and `analyses`.

A run whose stored data has gone missing fails the heavy filter rather than
aborting the query.

## The project registry

`silloncommon.registry` keeps a machine-wide index of projects
(`~/.config/sillon/registery.toml`, `%APPDATA%` on Windows) so `sillon projects`
can find them. Entries are located by resolved project path, so re-initialising
a project updates its row instead of appending one. Writes take a file lock. The
registry is an index, not data — deleting it loses nothing.

## Known limitations

- **Unix only.** The client and daemon talk over an `AF_UNIX` socket. A
  transport abstraction for Windows exists on the `windows_port` branch.
- **Deep project paths.** `AF_UNIX` socket paths are capped near 104 bytes and
  the socket lives inside the project; a deeply nested project cannot start its
  daemon.
- **Query memory.** `select_run_index` loads every run's JSON with no limit
  (~88 MB at 10,000 runs), and the heavy phase fetches one snapshot per
  survivor. Fine into the low thousands of runs.
- **Blocking commit.** The daemon commits on its event loop, so one large dump
  briefly stalls other clients of the same project.
