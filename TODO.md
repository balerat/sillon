# Todo

## Done (2.1)

- Bundles: `sillon export` / `sillon import`, the first code that reads sillon
  data back into a project
- Merging without a bundle: `sillon import <project>` and `--scan <tree>`
- `sillon init` with a `--storage-root` that readers honour
- `sillon check` / `--repair`
- Upward search for `.sillon/`, in the CLI, `load_project()` *and* the client —
  a run now joins the project containing its path instead of making a nested one
- `load_project` absorbed `open_project`
- Relocating a project is `mv`: the registry matches on project id and heals
  when the project is opened
- Lineage follows the uuid, not the name cached in the edge
- One reader for `config.toml`; storage root recorded relative to the project
- `started_at`, so runs from two machines can be ordered; a unique index on
  `uuid`; a schema version in `PRAGMA user_version`; migration across all four
  tables

## Done (2.0)

- SQLite WAL + indexes
- A machine-wide project registry — `sillon projects`, `sl.load_project("name")`
- Code versions, automatic lineage, a real diff engine, analysis provenance
- One vocabulary across the CLI and sillonlab
- Windows support, honest run status, errors that reach the caller

## Open

- Version is still single-sourced from `silloncommon.__version__`; fine, but it
  means the data layer owns the distribution's version number
- QR-code run uuid stamped onto figures
- Query at scale: `select_run_index` loads every run's JSON with no LIMIT
  (~88 MB at 10k runs) and the heavy phase fetches one snapshot per survivor
- The daemon commits on its event loop, so one large dump stalls other clients
- `versioncontrol.py` is dead code since `compare` was absorbed into `diff`
- Gate `publish.yml` on the test suite — v1.3.0 shipped broken because it is
  not, and nothing checks that the tag matches `__version__` either (v2.0.2
  was tagged against a tree that still said 2.0.1)
- `get_hash` pickles non-file values, so a hash is not stable across Python
  versions and `trace` cannot match the same value hashed elsewhere. Fixing it
  means canonical array hashing, which invalidates every stored digest.
- `started_at` for pre-2.1 runs is inferred from a naive local string, so it
  assumes the run was logged on the machine reading it

## Bigger, later

- Lineage inferred from value hashes (only worth it if runs feed each other)
- A shared-drive remote: `sillon remote add`, `sync`, `clone`. Deliberately not
  built — `export --dest /Volumes/share/` and `import` from it already work, so
  a remote only saves remembering the path and tracking which bundles have been
  read. Worth it when that bookkeeping actually becomes annoying.
- Live multi-device projects, as opposed to bundles passed between them. The
  object store turned out to be the easy half (it was already content- and
  uuid-addressed); the integer primary key was handled by re-pointing child
  rows rather than redesigning identity. What is left is genuinely hard: two
  machines writing at once, which is a different product.
