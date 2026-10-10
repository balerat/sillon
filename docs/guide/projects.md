# Working with projects

A project is any directory with a `.sillon/` folder. You never create one
explicitly — the first script that logs something does it for you.

## Finding your projects

Six months in, you will not remember where they all are. sillon keeps a registry
of every project it has created on this machine:

```bash
sillon projects
```

```text
╭─ Projects ─────────────────────────────────────────────────────────────────────╮
│                                                                                │
│  3 projects registered on this machine                                         │
│                                                                                │
│     Project             Runs     Last activity     Location                    │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│     Shaking Lattice     135      9d ago            /Users/you/phd/shaking      │
│     Thermal Sweep        41      48d ago           /Users/you/work/thermal     │
│     (unnamed)            2       92d ago           /Users/you/demo             │
│                                                                                │
╰────────────────────────────────────────────────────────────────────────────────╯
```

Unlike every other command, this one works from **any** directory — it answers
"where are my projects?", so it cannot require you to already be in one.

## Where a project begins and ends

A project is a directory with a `.sillon/` in it, and sillon finds it by
searching **upward** — like git. So a script in `scripts/sweeps/`, a notebook
in `analysis/`, and `sillon list` typed anywhere inside the tree all belong to
the same project:

```text
shaking/                 <- the project
  .sillon/
  scripts/sweeps/run.py  <- logs into shaking
  analysis/look.ipynb    <- sl.load_project() opens shaking
```

Sillon never nests projects. `sillon init` inside an existing one is refused,
and a run logged from a subdirectory joins the project above it rather than
making a second one.

### Making one deliberately

```bash
sillon init --name "Shaking Lattice"
```

You never have to: logging a run creates the project it needs, and that stays
true. `init` exists for the two things that side effect cannot do — naming a
project before it has runs, and putting the heavy data elsewhere:

```bash
sillon init --name "Shaking Lattice" --storage-root /Volumes/bigdisk/sillon
```

The database, `glob/`, `artifact/` and `figure/` then live on the big disk while
the project itself stays with your code. The root is recorded relative to the
project when it is inside it, so the project still survives being moved; an
external root is absolute by necessity and stays where it is.

### Moving a project

Use `mv`. A project carries its own identity in `.sillon/config.toml`, so the
next time you run sillon in it, this machine's registry is updated to point at
where it now is — no second row, no phantom to prune.

```bash
mv ~/scratch/shaking ~/Code/phd/shaking
cd ~/Code/phd/shaking && sillon        # the registry catches up here
```

| Flag | Effect |
|---|---|
| `--prune` | forget projects whose directory no longer exists |
| `--repair` | collapse duplicate entries left by older versions of sillon |
| `--no-stats` | skip run counts (does not open each database) |

Projects whose folder is gone are listed as `missing` rather than hidden — an
unmounted drive should not look the same as a project you never had.

## Naming a project

The name in the listing comes from `project_name`:

```python
with sp.track_run(project_name="Shaking Lattice"):
    ...
```

Runs logged without one show as `(unnamed)`. The name is recorded the first time
the project's daemon starts, so set it consistently.

## From Python

```python
import sillonlab as sl

for p in sl.list_projects():
    print(p["project_name"], p["run_count"], p["project_path"])

project = sl.load_project()                      # the one I am in
project = sl.load_project("Shaking Lattice")     # a unique prefix is enough
project = sl.load_project("~/phd/shaking")       # or a path
```

`load_project` takes a name or a path. A path that exists wins over a name, so
a project named after a directory you happen to be standing in cannot shadow
it. With no argument it searches upward from the current directory.

Each record has `project_name`, `project_path`, `project_storage`, `exists`,
and — unless you pass `with_stats=False` — `run_count` and `last_activity`.

## Where the registry lives

| Platform | Path |
|---|---|
| Linux | `$XDG_CONFIG_HOME/sillon/` or `~/.config/sillon/` |
| macOS | `~/.config/sillon/` |
| Windows | `%APPDATA%\sillon\` |

It is an index, not data. Deleting it loses nothing except the listing, and
projects re-register themselves the next time you log to them.

## Several projects, or one?

One project per *question*, not per script. Runs are only comparable inside a
project, so anything you will want to sort or diff together belongs in the same
one. Use tags to separate sub-experiments within it.

## Logging somewhere else

```python
with sp.track_run(project_path="/scratch/job-4821"):
    ...
```

Useful on a cluster, where the job's working directory is not your project.

`project_path` names a *location*, and the run joins the project that contains
it — searching upward, exactly as the CLI does. If there is no project above
that location, one is created there, which is what keeps logging zero-config.

!!! note "Changed in 2.1"
    Before 2.1 the path was taken literally, so a script run from
    `scripts/sweeps/` with `project_path="."` created a **second** project
    nested inside the first. Those runs are in a real project of their own —
    `sillon import --scan` will fold them back in.
