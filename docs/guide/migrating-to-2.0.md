# Migrating to 2.0

2.0 renames things so that one operation has one name, whichever surface you are
on. **The old names were removed, not aliased** — `sillon context` does not warn,
it does not exist.

Nothing about your stored data changes. Projects written by 1.x open unchanged.

## Command line

| 1.x | 2.0 | |
|---|---|---|
| `sillon context` | `sillon list` | and `context <run>` is now `show <run>` |
| `sillon search` | `sillon query` | matches `Project.query` |
| `sillon grab` | `sillon fetch` | matches `Run.fetch` |
| `sillon whose` | `sillon trace` | matches `Project.trace` |
| `sillon compare` | `sillon diff` | `compare` was already a thin shim over `diff` |

`sillon` with no command used to print the run table. It now shows the project
at a glance; the table is `sillon list`.

## sillonlab

| 1.x | 2.0 |
|---|---|
| `Run.fetch_result(name)` | `Run.fetch(name)` |
| `Project.find_by_hash(f)` | `Project.trace(f)` |
| `Project.compare(a, b)` | `Project.diff(a, b)` |
| `Project.context()` | `Project.runs()` |
| `Project.details(...)` | `Project.query(...)` |
| `sillonlab.delete_run(run)` | `run.delete()` or `project.delete_run(run)` |

New, because these were CLI-only and should not have been:

```python
project.versions()    # runs grouped by code version, like `sillon versions`
project.prune(...)    # free disk space, like `sillon prune`
project.name          # the project's own name, from its config
```

## sillonpy

| 1.x | 2.0 |
|---|---|
| `sp.log_metadata(...)` | `sp.add_metadata(...)` — they were the same function |
| `@sp.track` | `@sp.autolog` |

`track` and `track_run` differed by one word while doing categorically different
things: `@autolog` decorates a function and records its call, `track_run` is the
context manager that opens a run. Only the decorator was renamed.

## Finding what to change

```bash
grep -rn "sillon context\|sillon search\|sillon grab\|sillon whose\|sillon compare" .
grep -rn "fetch_result\|find_by_hash\|log_metadata\|sp\.track\b" .
```

## One thing worth doing after upgrading

The project name now lives in `.sillon/config.toml`, not only in this machine's
registry — so a copied project keeps its identity, and `sillon` can show it. An
existing project picks it up the next time you log a run with `project_name=`.
