# Quickstart

Five minutes: log a run, look at it, query it.

## 1. Log a run

Add three lines to a script you already have.

```python title="fit.py"
import numpy as np
import sillonpy as sp

with sp.track_run(run_name="my_fit", project_name="demo"):
    x = np.linspace(0, 10, 100)
    y = 1.3 * x + 5

    sp.log_param("degree", 1)          # what you chose
    coef = np.polyfit(x, y, 1)
    sp.log_result("coef", coef)        # what came out
    sp.add_tag("baseline")
```

Run it the way you always do:

```bash
python fit.py
```

No setup step, no `sillon init`. The first call creates `.sillon/` next to your
script and starts a background daemon to write into it.

## 2. Look at what you logged

```bash
sillon context
```

```text
╭─ Project ──────────────────────────────────────────────────────╮
│  1 runs logged in the project                                  │
│                                                                │
│    ID          Run Name   When        Params  Assets  Status   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│    39629020    my_fit     just now      1       1     SUCCESS  │
╰────────────────────────────────────────────────────────────────╯
```

Then the detail of one run:

```bash
sillon show my_fit
```

## 3. Read it back in Python

```python
import sillonlab as sl

project = sl.load_project()        # current directory
run = project.get("my_fit")

print(run.parameters)              # {'degree': 1}
coef = run.load_result("coef")     # the array, back from HDF5
```

## 4. Run it again

```bash
python fit.py
```

The second run is stored as `my_fit_2`. **sillon never overwrites a run** — if a
name is taken, it increments. Omit `run_name` entirely and you get a generated
one.

## 5. Query across runs

Once you have a handful of runs, ask questions of them:

```python
project = sl.load_project()

# Filter with plain Python. No query language.
good = project.query(
    tags="baseline",
    parameters={"degree": lambda d: d <= 3},
)

best = good.sort_by("rmse")[:5]        # the five lowest rmse
print(best.to_dataframe())
```

or from the shell:

```bash
sillon search -p degree=1 -t baseline
```

## Where to go next

- [Core concepts](concepts.md) — the five-minute mental model. Worth reading once.
- [Logging runs](../guide/logging.md) — the whole logging API.
- [Querying and analysis](../guide/analysis.md) — working with many runs.
- [Examples](https://github.com/balerat/sillon/tree/main/examples) — runnable projects, including a parameter sweep.
