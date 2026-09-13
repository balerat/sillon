# Core concepts

Five ideas. Read this once and the rest of the documentation is obvious.

## Project

A directory containing a `.sillon/` folder. That is the whole definition — there
is no registration step, no config to write. The first script that logs
something creates it.

Projects are independent: one database, one set of runs, one place to back up.
`sillon projects` lists every project on your machine and where it is.

## Run

One execution of your script. A run holds:

| | |
|---|---|
| **parameters** | the inputs you chose — `log_param` |
| **results** | the outputs you got — `log_result` |
| **artifacts** | files you produced — `log_result(path=...)` |
| **figures** | plots, with a record of what drew them — `log_figure` |
| **metadata** | context: host, author, source code, timing — mostly automatic |
| **tags / notes** | your own labels — `add_tag`, `add_note` |

Runs are never overwritten. Log `my_fit` twice and you get `my_fit` and
`my_fit_2`.

### Parameters vs results

The distinction is *intent*, not type: a parameter is something you decided, a
result is something the run produced. Keeping them apart is what makes
`query(parameters={...})` answer "which settings did I try?" and
`sort_by("rmse")` answer "which worked best?".

### Run status

Every run records how it ended, and this is meant to be trusted:

| Status | Meaning |
|---|---|
| `SUCCESS` | the script finished normally |
| `CRASHED` | it raised an uncaught exception, or was killed |
| `RUNNING` | still in flight |

A run that died is never recorded as a success. When it crashed with an
exception, the type and message are stored too (`sillon.error.type`,
`sillon.error.message`).

## Light values and heavy values

You log both the same way; sillon decides where they go.

- **Small, JSON-friendly values** (numbers, strings, short lists) are stored
  inline in SQLite, so filtering on them is fast.
- **Large arrays** are written to the run's HDF5 store and the database keeps a
  pointer, its shape and its dtype.

This is why `log_result("field", a_huge_array)` needs no special handling, and
why filtering on a parameter stays fast even when the results are gigabytes.

## Two-phase queries

`project.query(...)` is deliberately split:

1. **Cheap phase** — filters that only need the database (parameters, tags,
   status, dates) run first, in memory, over one bulk fetch.
2. **Heavy phase** — filters that need the array store run *only* on the runs
   that survived phase one.

So this is fast even in a large project, because the `results` filter only ever
touches a handful of files:

```python
project.query(
    parameters={"degree": lambda d: d == 3},   # cheap, narrows to a few runs
    results={"rmse": lambda v: v < 0.1},       # heavy, runs only on those
)
```

Order your filters cheapest-first and you get this for free.

## The daemon

Your script does not write to the database. It sends what you log to a small
background process — one per project — which owns the writes.

You never start or stop it. It appears on the first log call and exits on its
own after five minutes idle (`SILLON_IDLE_TIMEOUT` to change that). Several
scripts can log to the same project at once; the daemon serialises them.

Two consequences worth knowing:

- If your script is killed outright, the daemon notices the dropped connection
  and marks that run `CRASHED` rather than losing it.
- Its log is at `.sillon/daemon.log`. That is the first place to look when
  something is wrong.

## Content hashing

Every logged value is hashed. Two runs that produced identical data have the
same hash, which is what makes `sillon whose <file>` able to tell you which run
a file on disk came from.

## Lineage

A run can record that it derives from another:

```python
with sp.track_run(inherit="baseline"):
    ...
```

Nothing is copied — it is an edge you can query later with `run.parents()`,
`run.children()`, or `sillon lineage <run>`.
