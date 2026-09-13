# CLI reference

```bash
sillon <command> [options]
sillon --help
sillon --version
```

Run `sillon` with no command for the project overview.

Every command except `projects` must be run from inside a project (a directory
containing `.sillon/`). Runs can be named by **name, full uuid, or an unambiguous
uuid prefix** — `sillon show a3f9` works.

---

## Exploring

### `sillon context` — project overview

```bash
sillon context              # every run
sillon context my_fit       # detail cards for named runs
```

The default when you type bare `sillon`.

### `sillon show` — one run in detail

```bash
sillon show my_fit
sillon show my_fit -p                 # parameters
sillon show my_fit -r                 # results
sillon show my_fit -m %all%           # all metadata
sillon show my_fit -f                 # figures, with their provenance
sillon show my_fit -A                 # everything
```

| Flag | Shows |
|---|---|
| `-p [KEY ...]` | parameters (all, or named ones) |
| `-r [KEY ...]` | results |
| `-m [KEY ...]` | metadata — `%all%` for everything |
| `-t` | tags |
| `-f` | figures and what they were built from |
| `-n` | notes |
| `-A` | all of the above |

### `sillon search` — find runs

```bash
sillon search -p degree=3
sillon search -p degree=3 lr=0.01 -t baseline
sillon search --status SUCCESS --after 2026-01-01
sillon search -r coef                      # runs that have this result
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

### `sillon compare` — what differs between two runs

```bash
sillon compare baseline refined
```

Parameters, metadata and source differences. Takes exactly two runs.

### `sillon whose` — which run produced this file

```bash
sillon whose figures/fit.png
sillon whose 9f2c8a1e...            # or a bare SHA-256
```

---

## Getting data out

### `sillon grab` — one item as a file

```bash
sillon grab my_fit -r coef
sillon grab my_fit -r coef --dest out/
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

Both commands prompt before doing anything. `-y` skips the prompt.

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
