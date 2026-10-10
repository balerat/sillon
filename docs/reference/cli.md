# CLI reference

```bash
sillon <command> [options]
sillon --help
sillon --version
```

Run `sillon` with no command for the project at a glance — its name, run count
and health, code versions, storage and whether the daemon is up. Outside a
project it tells you how to find your projects instead of erroring.

Every command except `projects` and `init` must be run from inside a project.
"Inside" means what it means in git: the project is found by searching **upward**
for a `.sillon/` directory, so `sillon list` works from `analysis/figures/`.

Runs can be named by **name, full uuid, or an unambiguous uuid prefix** —
`sillon show a3f9` works.

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

### `sillon init` — make a directory a project

```bash
sillon init
sillon init --name "Shaking Lattice"
sillon init --storage-root /Volumes/bigdisk/sillon    # heavy data elsewhere
sillon init ~/Code/phd/new-thing                      # somewhere else
```

Logging a run has always created the project it needs, and still does — that is
the point of sillon, and `init` is not required. What `init` adds is the two
things that side effect cannot do: name a project before it has any runs, and
put its heavy data somewhere other than `.sillon/`.

| Flag | Effect |
|---|---|
| `--name NAME` | The project's name. Without it the first run that passes `project_name` sets it. |
| `--storage-root PATH` | Where `glob/`, `artifact/`, `figure/` and the database live. Recorded relative to the project when it is inside it, so the project still travels. |

Running it on an existing project reports and changes nothing — it will not
rename a project or move its data. Running it *inside* one is refused: sillon
does not nest projects.

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

### `sillon report` — a run written up for a person

```bash
sillon report my_fit
sillon report my_fit --with-data --dest out/
```

A zip holding `manifest.json` and a readable `report.md`, for sending to a
colleague. It is **lossy on purpose**: results over 512 bytes are recorded as a
size rather than a value, and artifact bytes and figure images are never
included, even with `--with-data`. Nothing reads one back.

To move runs *to another machine*, that is [`export`](#sillon-export-runs-as-a-portable-bundle).

---

## Moving runs between machines

A bundle is the machine-readable counterpart of `report`: everything needed to
reconstruct a run somewhere else, and nothing else. See
[Moving runs](../guide/transfer.md).

### `sillon export` — runs as a portable bundle

```bash
sillon export                              # the whole project, with its data
sillon export deg3 deg4                    # just these
sillon export -t sweep -p degree=3         # whatever the filters match
sillon export --dest /Volumes/share/       # a directory gets a generated name
sillon export --no-data                    # the records only
```

Takes the same filters as [`query`](#sillon-query-find-runs), so there is one
filter vocabulary rather than two. With no runs and no filters it exports
everything.

| Flag | Effect |
|---|---|
| `--dest PATH` | A file to write, or a directory to write a self-describing name into (`<project>~<host>~<when>.sillon`). Defaults to the current directory. |
| `--no-data` | Index only — no arrays, artifacts or figures. The runs import as **stubs**: the record is there, reading the data is not. |
| `-p` / `-m` / `-t` / `--status` / `--before` / `--after` | As in `query`. |

A run whose data a row claims but disk does not have — a pruned run — exports
its record and says so, rather than producing a bundle that looks complete.

### `sillon import` — add what you do not already have

```bash
sillon import lattice~laptop~20261007T185407Z.sillon   # a bundle
sillon import ~/old-phd/shaking                        # another project
sillon import --scan ~/Code/phd                        # every project under it
sillon import --dry-run bundle.sillon      # what would happen, changing nothing
sillon import --inspect bundle.sillon      # what is in it, ignoring this project
sillon import --no-data bundle.sillon      # the records only
```

The source is a **bundle file** or **another project directory** on this
machine. Crossing a machine boundary needs a bundle; merging two projects that
are both right here does not, so there is no packing step for that.

| Flag | Effect |
|---|---|
| `--scan` | Treat the source as a directory to search, and import every project under it. This project is left out of its own scan. |
| `--dry-run` | Print the plan and change nothing. The plan shown is the plan that would be carried out, names and all. |
| `--inspect` | Describe one source without looking at this project at all — works for a bundle you have not decided about yet. |
| `--no-data` | Records only. |

**Union, never overwrite.** A run already here is left exactly as it is; a run
that is not is added. Nothing an import does can lose local work, which is why
it is safe to repeat — and repeating is the normal case, since re-importing is
how you find out whether a bundle has anything new in it.

| Situation | What happens |
|---|---|
| the run is already here (same uuid) | skipped and counted |
| the name is free | added as it was |
| the name is taken | added as `<name>~<origin host>` |
| a lineage edge points at a run in neither project | the edge is kept and reported |

Identity is the run's uuid, which has been globally unique since the beginning.
Names are not identity — two machines will both produce a `deg3` — so the
incoming one is suffixed and the local one keeps its name. Lineage is unaffected
either way, because edges are followed by uuid.

The suffix names whatever actually distinguishes the source: the **machine** for
a bundle (`deg3~laptop`), the **project** for a directory on this one
(`deg3~Alpha`), since both projects share a hostname and it would say nothing.

Everything is preserved: the uuid, both timestamps, the status, the hostname,
the author, and the version of sillon that wrote the run — not the one importing
it.

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

## Health

### `sillon check` — what no longer adds up

```bash
sillon check
sillon check --repair      # apply the fixes that cannot lose anything
```

Most of what sillon records is a cross-reference, and each one can come apart:
a pruned run, a half-finished copy, a child imported without its parent, a
project moved while its data was on a disk that is not here. None of it is
fatal, and all of it is confusing when you first meet it as a failed read six
months later.

Findings come in three severities, worst first:

| | Meaning | Examples |
|---|---|---|
| `broken` | already failing | two runs sharing a uuid; a storage root that is not there; a database that will not open |
| `stale` | will mislead | a run whose data is gone; a lineage edge pointing at a run that is not here; a source a code version refers to but that is not stored |
| `tidy` | wasted space | data no run claims; stored source text no run refers to |

`--repair` applies only the findings it cannot be wrong about in a costly way:
re-registering the project, and deleting data and source blobs that no run row
refers to. **It never touches a run row.** Anything whose fix is a judgement
call — a run whose data is gone might want re-running or might want deleting —
is reported and left for you.

It is also the one command that works on a project which will not open: if the
database cannot be read, that is the first finding rather than the reason you
cannot ask.

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
