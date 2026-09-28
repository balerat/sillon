# CLI reference

```bash
sillon <command> [options]
sillon --help
sillon --version
```

Run `sillon` with no command for the project at a glance — its name, run count
and health, code versions, storage and whether the daemon is up. Outside a
project it tells you how to find your projects instead of erroring.

Every command except `projects` must be run from inside a project (a directory
containing `.sillon/`). Runs can be named by **name, full uuid, or an unambiguous
uuid prefix** — `sillon show a3f9` works.

!!! warning "Renamed in 2.0"
    `context` → `list`, `search` → `query`, `grab` → `fetch`, `whose` → `trace`,
    and `compare` is gone in favour of `diff`. There are no aliases; see
    [Migrating to 2.0](../guide/migrating-to-2.0.md).

---

## Exploring

### `sillon list` — the runs, as a table

```bash
sillon list              # every run
sillon list my_fit a3f9  # just these
```

Many runs at a glance. For one run in detail, that is `sillon show`.

### `sillon show` — one run in detail

```bash
sillon show my_fit
sillon show my_fit -p                 # parameters
sillon show my_fit -r                 # results
sillon show my_fit -m %all%           # all metadata
sillon show my_fit -f                 # figures, with their provenance
sillon show my_fit -A                 # analyses, with their provenance
```

| Flag | Shows |
|---|---|
| `-p [KEY ...]` | parameters (all, or named ones) |
| `-r [KEY ...]` | results |
| `-m [KEY ...]` | metadata — `%all%` for everything |
| `-t` | tags |
| `-f` | figures and what they were built from |
| `-A` | analyses and what they were computed from |
| `-n` | notes |

### `sillon query` — find runs

```bash
sillon query -p degree=3
sillon query -p degree=3 lr=0.01 -t baseline
sillon query --status SUCCESS --after 2026-01-01
sillon query -r coef                      # runs that have this result
```

| Flag | Filter |
|---|---|
| `-p KEY=VALUE` | parameter equals value |
| `-m KEY=VALUE` | metadata equals value |
| `-t TAG` | has tag |
| `-r RESULT` | has this result |
| `-a ARTIFACT` | has this artifact |
| `-A ANALYSIS` | has this analysis |
| `--status` | run status |
| `--before` / `--after` | date bounds |
| `--limit` | cap the number of results |

Values are parsed as Python literals, so `-p lr=0.01` compares as a float.

### `sillon versions` — group runs by the code that produced them

```bash
sillon versions                # every code version in the project
sillon versions c8d012         # the per-file breakdown of one version
sillon versions --backfill     # recover versions for runs logged before this existed
```

A run's code version covers its **entry script and your own modules**, hashed at
the AST level with literal values normalised away — so a tuned constant
(`N = 5` → `N = 4`) does *not* start a new version, while a changed expression
does. See [Code versions](../guide/provenance.md#code-versions).

| Flag | Effect |
|---|---|
| `--backfill` | Recover versions for older runs from their stored entry script. Those cover the entry script only and are shown as such. |
| `--files` | Per-file hashes (implied when you name a version). |

### `sillon projects` — every project on this machine

```bash
sillon projects
sillon projects --prune        # forget projects whose folder is gone
sillon projects --repair       # collapse duplicates from older versions
sillon projects --no-stats     # skip run counts
```

The one command that works from any directory. See [Projects](../guide/projects.md).

---

## Provenance

### `sillon lineage` — what a run came from

```bash
sillon lineage refined
```

Shows the run's parents (`↑`) and the runs derived from it (`↓`).

### `sillon diff` — what differs between runs

```bash
sillon diff baseline refined            # compare two runs
sillon diff baseline refined --source   # ...and show the source diff
sillon diff --across tag=sweep          # what varies across a set
sillon diff --across                    # ...across the whole project
```

Reports parameters with a real delta, whether the code differed **in logic or
only in a tuned constant**, and whether the results moved. Arrays are compared
by shape, dtype and hash — never element by element — so a diff stays fast on
large results.

```text
  Parameter    From    To     Δ
  degree       3       5      (+66.67%)

Code  same logic 4756b7f9 — constants differ in run.py

  Result   From              To                 
  coef     float64 (4,)      float64 (6,)        shape changed
  rmse     9.7456762644862…  6.1295293145338…    (-37.11%)
  field    float64 (5000,)   float64 (5000,)     contents differ
```

`--across` answers the question a sweep leaves behind — which knobs were
actually turned:

```text
  varying   degree: 1, 2, 3, 4, 5
  varying   ridge: 0.0, 0.1
  constant  seed, solver
  code      one version (98167c00)
```

When a set spans more than one code version it says so, because those runs are
not all comparable.

| Flag | Effect |
|---|---|
| `--across [KEY=VALUE ...]` | Summarise a set instead of comparing two. `tag=sweep`, `status=SUCCESS`, or nothing for the whole project. |
| `--source` | Also print the unified source diff. |
| `--max-bytes N` | Largest result to load for comparison (default 64 MB). Bigger ones are compared by shape and dtype and reported as not compared. |

### `sillon like` — runs similar to a given one

```bash
sillon like happy_perlman
sillon like happy_perlman --limit 5
```

*"Did I do something close to this?"* — ranked by how much of the configuration
two runs share, with a tiebreak on how far the differing values moved, so
`degree 3→2` ranks above `degree 3→5`.

```text
  Match   Run         Differences                  Code
    75%   d2_r0.0     degree 3→2                   same
    75%   d4_r0.0     degree 3→4                   same
    50%   d2_r0.1     degree 3→2, ridge 0.0→0.1    same
    17%   unrelated   different parameter set      —
```

More useful than an exact-duplicate check, which only fires on a perfect repeat
and says nothing about the near misses.

### `sillon trace` — which run produced this file

```bash
sillon trace figures/fit.png
sillon trace 9f2c8a1e...            # or a bare SHA-256
```

---

## Getting data out

### `sillon fetch` — one item as a file

```bash
sillon fetch my_fit -r coef
sillon fetch my_fit -r coef --dest out/
```

### `sillon report` — a self-contained bundle

```bash
sillon report my_fit
sillon report my_fit --with-data --dest out/
```

---

## Editing

### `sillon add` — annotate a run

```bash
sillon add my_fit -n "Used in figure 3"
sillon add my_fit -t publication reviewed
sillon add run_a run_b -t sweep          # several runs at once
```

### `sillon rename`

```bash
sillon rename old_name new_name
```

---

## Deleting

`delete` always prompts. `prune` prompts only for `--delete-metadata`, because
that is the irreversible half — a data-only prune leaves the record intact and
can be re-created by re-running. `-y` skips either prompt.

### `sillon delete` — remove runs

```bash
sillon delete my_fit
sillon delete run_a run_b -y
```

Removes the database row **and** the stored data.

### `sillon prune` — reclaim space

```bash
sillon prune --older-than 30d
sillon prune --older-than 2026-01-01
sillon prune --run-id a3f9 b7c2
sillon prune --older-than 90d --delete-metadata
```

By default prune deletes the **stored data** and keeps the database row, so the
record of what you ran survives. `--delete-metadata` removes the rows too — a
different and irreversible thing, which the prompt says explicitly.

Prune refuses to run without a scope: you must give `--run-id` or `--older-than`.

---

## Environment variables

| Variable | Effect |
|---|---|
| `SILLON_IDLE_TIMEOUT` | seconds before an idle daemon exits (default 300) |

---

## Not implemented yet

`sillon run`, `sillon watch`, `sillon estimate` and the GUI appear in the
roadmap but do not exist. If a command is not listed on this page, it is not
there.
