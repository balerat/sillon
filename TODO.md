# Todo

## Done (2.0)

- SQLite WAL + indexes
- A machine-wide project registry — `sillon projects`, `sl.open_project("name")`
- Code versions, automatic lineage, a real diff engine, analysis provenance
- One vocabulary across the CLI and sillonlab
- Windows support, honest run status, errors that reach the caller

## Open

- `load_project()` should search upwards for a `.sillon/`, so it works from a
  subdirectory the way `git` does
- Version is still single-sourced from `silloncommon.__version__`; fine, but it
  means the data layer owns the distribution's version number
- QR-code run uuid stamped onto figures
- Query at scale: `select_run_index` loads every run's JSON with no LIMIT
  (~88 MB at 10k runs) and the heavy phase fetches one snapshot per survivor
- The daemon commits on its event loop, so one large dump stalls other clients
- `versioncontrol.py` is dead code since `compare` was absorbed into `diff`
- Gate `publish.yml` on the test suite — v1.3.0 shipped broken because it is not

## Bigger, later

- Lineage inferred from value hashes (only worth it if runs feed each other)
- Multi-device projects: needs run identity off the integer primary key and a
  content-addressed object store. Business-shaped; not before someone needs it.
