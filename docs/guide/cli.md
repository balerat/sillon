# Command line

The `sillon` command explores the runs in a project. Run it from inside a project directory (one
containing a `.sillon/` folder).

```bash
sillon --help        # list commands
sillon --version     # print the installed version
sillon               # bare command → the project overview
```

Runs can be referenced by name, full uuid, or an unambiguous **uuid prefix** (e.g. `a3f9`).

## Browsing

```bash
# Overview of all runs, or a detail card per run
sillon context [run_id ...]

# Full run card (params, results+sizes, figures, analyses, tags, notes)
sillon show [run_id]

# ...or just specific sections:
sillon show [run_id] -p [params] -r [results] -m [metadata]   # key filters
sillon show [run_id] -t        # tags
sillon show [run_id] -f        # figures (with their data provenance)
sillon show [run_id] -A        # analyses
sillon show [run_id] -n        # notes

# Compare two runs (parameter and source diff)
sillon compare [run_id_A] [run_id_B]
```

## Searching

Filter by parameter/metadata value, tag, status, date, or the presence of a result/artifact:

```bash
sillon search -p optimizer=adam lr=0.01      # parameter equality
sillon search -m sillon.language=python      # metadata equality
sillon search -t baseline                    # has tag
sillon search --status SUCCESS               # column filter
sillon search --after 2026-06-01             # date range (--before / --after)
sillon search -r coef -a mesh                # has result / has artifact
sillon search -t prod --limit 20
```

!!! note "Value *predicates* are a Python feature"
    The shell can express equality and presence; for predicates like `loss < 0.1` use
    `project.query(results={"loss": lambda v: v < 0.1})` in [`sillonlab`](analysis.md).

## Annotating & renaming

```bash
sillon add [run_id] --note "kept for the paper" --tag production

# Rename a run (rejected if the new name already exists)
sillon rename [run_id] [new_name]
```

## Tracing a file back to its run

```bash
# Hash a file (e.g. a stray figure) and report which run + figure/artifact owns it
sillon whose path/to/figure.png
```

## Retrieving, reporting, and cleanup

```bash
# Fetch a result / artifact / figure to a file on disk
sillon grab [run_id] -r [result_name] --dest [dir]

# Export a self-contained context bundle (manifest + readable report + source) as a zip
sillon report [run_id] --dest [out.zip] [--with-data]

# Free disk space: drop a run's stored data (keeps its metadata by default)
sillon prune --run-id [id] --older-than 30d [--delete-metadata]

# Permanently delete a run (data + database row)
sillon delete [run_id] [-y]
```

`prune --delete-metadata` and `delete` are irreversible, so they prompt for confirmation
(pass `-y` to skip it).

> Planned for a future release (not yet available): `watch` (live TUI), `estimate` (resource
> prediction), `source` (standalone source viewer), and `run` (relaunch/reproduce).
