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

### Transport

Client and daemon exchange those frames over a connected stream socket. Which
kind is the only platform-dependent part of the system, and it lives entirely in
`silloncommon.transport`:

| Transport | Endpoint | Used when |
|---|---|---|
| `unix` | `AF_UNIX` socket at `.sillon/daemon.sock` | `socket.AF_UNIX` exists (Linux, macOS) |
| `tcp` | `AF_INET` on `127.0.0.1`, ephemeral port in `.sillon/daemon.port` | it does not (Windows) |

Selection is by capability (`hasattr(socket, "AF_UNIX")`) rather than by
`sys.platform`, so if CPython ever ships Unix sockets on Windows this picks them
up with no code change. `SILLON_TRANSPORT=unix|tcp` forces one — that is how the
Windows path is tested on POSIX CI.

Both transports carry the same framing, the same JSON-RPC layer and the same
`selectors` loop; only `bind`/`connect` differ. Named pipes were rejected for
exactly that reason: `selectors` cannot poll pipe handles, so the daemon would
need a second event loop.

A loopback TCP port is reachable by any local process, so the daemon writes a
random secret to `.sillon/daemon.token` and every client presents it in its
REGISTER frame — the first frame on every connection. Commands on a connection
that has not registered are refused. The check runs on both transports, which
also closes the hole where any local user able to traverse the project directory
could drive the Unix socket.

## Storage layout

```
.sillon/                 the project marker; found by searching upward
  config.toml            project id, project name, storage root
  staging/               short-lived handoff files for large arrays
  daemon.log / .pid / .sock / .port / .token / .lock

<storage root>/          `.sillon` unless config.toml says otherwise
  database.sql           SQLite: one row per run + artifact/figure/analysis rows
  glob/<uuid>/glob.hdf5  heavy results, big-array params, analyses, source
  artifact/<uuid>/...    copied result files
  figure/<uuid>/...      logged figures
  sources/<sha256>       content-addressed source text behind each code version
```

Everything a run owns is keyed by the **run uuid** and everything a code version
owns is keyed by **content**, which is why an import is a directory copy: see
`silloncore.bundle`. Artifact and figure rows store a uuid *folder name*, not a
path, resolved at read time against the run's own directory — so a whole
`<uuid>/` tree moves with every pointer inside it still valid.

`silloncommon.project_config` is the only place `config.toml` is parsed, shared
by the client, the daemon and both interfaces. The storage root is recorded
relative to the project when it is inside it, so a project survives being moved;
three modules used to parse this file independently and two of them disagreed.

SQLite is opened in WAL mode with `busy_timeout` and `synchronous=NORMAL`, so
reading a project (a CLI command, a notebook) never blocks the daemon writing to
it. Indexes exist on `uuid`, `name`, `date`, `started_at`, `logic_version`,
`status` and the three `run_id` foreign keys, plus a unique index on `uuid` so a
run cannot be imported twice. All of it is applied to existing databases on
open, by `migrate_schema`, which also records a schema version in
`PRAGMA user_version` and backfills `started_at` from `date`.

### Timestamps

A run records both `date` (`%Y-%m-%d-%H:%M:%S`, naive local, what gets
displayed) and `started_at` (ISO-8601 with an offset, what gets ordered).
`select_run_index` carries a precomputed `when` key; everything that sorts or
bounds by time uses it, because a naive local time cannot order runs from two
machines.

## Reading and querying (the engine)

Both the CLI and `sillonlab` go through `silloncore.engine`; neither touches the
database or the globs directly. Key entry points: `get_run_snapshot`,
`load_run_result` / `load_run_parameter` / `load_run_analysis`, `export_run` /
`export_run_report`, `export_bundle` / `import_from` / `scan_and_import`,
`prune_runs` / `delete_run`, `check_project`, and `query_runs`.

### Two-phase queries

`query_runs` is split so glob reads stay rare:

- **Cheap phase** — one bulk `select_run_index` fetch, filtered in memory on
  everything that lives in the database (parameters, metadata, tags, dates,
  status, presence checks). No HDF5 file is opened.
- **Heavy phase** — only the survivors have their glob read, for value
  conditions on `results` and `analyses`.

A run whose stored data has gone missing fails the heavy filter rather than
aborting the query.

## Moving runs between projects

`silloncore.bundle` owns the bundle format (write, read, inspect) and
`silloncore.transfer` the import. They are separate because a bundle file and a
project directory are two *sources* feeding one importer: both implement
`describe` / `run_uuids` / `read_run` / `copy_run_data` / `copy_sources`, and
`transfer.import_source` does not know which it was handed.

The rule is union-never-overwrite, keyed on the run uuid. A colliding *name*
gets the incoming run suffixed — which is load-bearing, not cosmetic: it is what
keeps names unique within a project, and therefore what lets name-keyed lookups
go on returning one run. Lineage does not depend on it, because edges are
followed by uuid.

`insert_imported_run` is the sibling of `insert_simulation`, which cannot be
reused for this: it is duck-typed on a live `Simulation`, and
`Simulation.__init__` stamps `date = now()` and mints a name.

## The project registry

`silloncommon.registry` keeps a machine-wide index of projects
(`~/.config/sillon/registery.toml`, `%APPDATA%` on Windows) so `sillon projects`
can find them. Entries are located by resolved project path **then by project
id**, so re-initialising a project updates its row and a project that has been
moved is recognised rather than registered twice — `register_if_moved` runs
whenever a project is opened. Writes take a file lock. The registry is an index,
not data — deleting it loses nothing.

`silloncore.projects.create_project` is the one implementation of "make this
directory a project", shared by `sillon init` and the daemon, so a project that
comes into existence as a side effect of the first logged run is identical to
one made deliberately.

## Known limitations

- **Deep project paths (POSIX only).** `AF_UNIX` socket paths are capped near
  104 bytes and the socket lives inside the project, so a deeply nested project
  cannot start its daemon. The TCP transport has no such limit.
- **Query memory.** `select_run_index` loads every run's JSON with no limit
  (~88 MB at 10,000 runs), and the heavy phase fetches one snapshot per
  survivor. Fine into the low thousands of runs.
- **Blocking commit.** The daemon commits on its event loop, so one large dump
  briefly stalls other clients of the same project.
- **No shared-filesystem projects.** A `.sillon/` on NFS or SMB cannot be
  driven from two machines: `AF_UNIX` sockets are not meaningful across a
  network filesystem, the TCP fallback publishes a bare port with no host, and
  WAL locking is unreliable there. Bundles are the supported way across
  machines, and they only ever read and write whole files.
- **Hashes of in-memory values are not portable.** `get_hash` falls back to
  `pickle.dumps` for anything that is not a file, and pickle output is not
  guaranteed stable across Python versions. `sillon trace` may therefore fail
  to recognise the same value hashed on a different interpreter. Imports are
  unaffected: they dedup on uuid.
