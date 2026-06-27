# Command line

The `sillon` command explores the runs in a project. Run it from inside a project directory (one
containing a `.sillon/` folder).

```bash
sillon --help
```

## Browsing

```bash
# Overview of all runs, or a detail card per run
sillon context [run_id ...]

# Detailed parameters / results / metadata
sillon show [run_ids] -p [parameters] -r [results] -m [metadata]

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

## Annotating

```bash
sillon add [run_id] --note "kept for the paper" --tag production
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

> Planned for a future release (not yet available): `watch` (live TUI), `estimate` (resource
> prediction), `source` (standalone source viewer), and `run` (relaunch/reproduce).
