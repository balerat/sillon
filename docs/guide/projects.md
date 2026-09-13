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
╭─ Projects ──────────────────────────────────────────────────────╮
│  3 projects registered on this machine                          │
│                                                                 │
│    Project              Runs   Last activity   Location         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│    Shaking Lattice      135    9d ago          /Users/you/phd…  │
│    Thermal Sweep         41    48d ago         /Users/you/work… │
│    (unnamed)              2    92d ago         /Users/you/demo  │
╰─────────────────────────────────────────────────────────────────╯
```

Unlike every other command, this one works from **any** directory — it answers
"where are my projects?", so it cannot require you to already be in one.

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

project = sl.open_project("Shaking Lattice")     # a unique prefix is enough
project = sl.open_project("~/phd/shaking")       # or a path
```

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
