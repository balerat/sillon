# Migrating to 2.1

2.1 is mostly additive — projects can now move between machines, and there is
tooling for the project itself. Two things change behaviour, and one name is
removed.

Nothing needs doing to your data. An existing project is brought forward the
first time 2.1 opens it, with no migration step and nothing moved on disk.

## `sl.open_project` is gone — use `sl.load_project`

They were two names for one operation, which is the duplication 2.0 spent a
release removing. `load_project` now takes what `open_project` took.

```python
sl.open_project("Shaking Lattice")       # before
sl.load_project("Shaking Lattice")       # now
```

A path that exists wins over a registered name, so a project named after a
directory you happen to be standing in cannot shadow that directory.

## A run joins the project it is inside

`project_path` names a *location*, and the run now joins the project that
contains it — searching upward, exactly as the CLI does.

Before 2.1 the path was taken literally. So a script in `scripts/sweeps/` run
with `project_path="."` created a **second project nested inside the first**:

```text
shaking/
  .sillon/                 <- your project
  scripts/sweeps/
    .sillon/               <- and this, which you probably did not want
```

Now that run lands in `shaking/`. If there is no project anywhere above the
path, one is still created there, so logging stays zero-config.

**If you have stray nested projects**, their runs are real and nothing was
lost. Fold them in:

```bash
cd shaking
sillon import --scan .
```

Then delete the leftover `.sillon/` directories once `sillon list` shows the
runs where you want them.

## Everything else is additive

| New | What for |
|---|---|
| `sillon export` / `sillon import` | [Moving runs between machines](transfer.md) |
| `sillon import --scan` | merging a tree of projects |
| `sillon init` | naming a project before it has runs; `--storage-root` |
| `sillon check` / `--repair` | [what no longer adds up](../reference/cli.md#sillon-check-what-no-longer-adds-up) |
| `Project.export`, `.import_from`, `.import_tree`, `.check`, `.repair` | the same from Python |
| `Run(uuid=...)` | a handle that follows identity rather than a name |

## What changed underneath

You should not have to care about any of this, but it explains a few things
you might notice.

**Runs now record an offset-aware timestamp** (`started_at`) alongside the
`date` string you already see. `date` is unchanged and still what gets
displayed; the new one is what orders runs, because a naive local time cannot
order runs from two machines. Existing runs are backfilled on first open, using
the offset in force on each run's own date — which assumes the run was logged
on the machine reading it. True for a project that has only ever lived there;
off by an offset for anything you copied in by hand before 2.1.

**`--older-than` and `--before`/`--after` compare real instants**, so a cutoff
means the same thing for runs from different machines. `sillon prune` also now
refuses a date it cannot parse rather than comparing and getting it wrong.

**`uuid` is unique.** A project that somehow already holds two runs with the
same uuid still opens — the constraint is simply not applied — and
`sillon check` reports it.

**Lineage follows the uuid, not the name.** A parent edge records both; the
name is the one the parent had on the machine where the link was made, which
after an import may belong to a different run locally. `run.parents()` follows
the uuid. Reading `run.name` on a handle built from a uuid loads the run, so
the name you get is its name *here*.

**The storage root is recorded relative to the project** when it is inside it,
and readers honour it. Before 2.1 it was absolute and readers ignored it, so a
moved project kept working while the next run it logged wrote its data back to
the path the project had left. Existing projects are rewritten on first open;
no data moves.

**The source store lives under the storage root** (`sources/`) rather than
beside the project. Identical in the default layout, where the storage root
*is* `.sillon`, so nothing migrates.

## Still true from 2.0

The [2.0 renames](migrating-to-2.0.md) are unchanged: `context` → `list`,
`search` → `query`, `grab` → `fetch`, `whose` → `trace`, `compare` → `diff`,
`log_metadata` → `add_metadata`, `@track` → `@autolog`.
