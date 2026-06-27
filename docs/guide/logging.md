# Logging runs

You log runs from inside your simulation script with the **`sillonpy`** client. A run captures
parameters, results, metadata, tags, notes, figures, and your script's source — written to a
local `.sillon/` store by a background server that `sillonpy` starts for you.

```python
import sillonpy as sp
```

## Start a run

```python
sp.init(run_name="my_fit", project_name="demo")
```

`init` attaches the script to a project (a `.sillon/` folder, created on first use). Useful
optional arguments: `project_path=` (where the `.sillon/` lives, defaults to the working
directory), `author=`, `organisation=`.

!!! tip "Names never clash"
    If `run_name` already exists, sillon auto-increments it (`my_fit`, `my_fit_2`, …), so
    re-running a script never overwrites a previous run.

## Parameters

```python
sp.log_param("learning_rate", 0.01)
sp.log_param({"optimizer": "adam", "epochs": 100})   # a dict logs several at once
sp.log_param(seed=42)                                 # or keyword arguments
```

Small values are stored inline in the database (and are fast to query). **Large NumPy arrays are
offloaded to HDF5 automatically** — you log them the same way:

```python
import numpy as np
sp.log_param("grid", np.linspace(0, 1, 100_000))      # stored in the glob, not the DB
```

## Results

```python
sp.log_result("final_loss", 0.012)                    # a metric
sp.log_result("coef", np.polyfit(x, y, 1))            # an array -> HDF5 glob
sp.log_result("checkpoint", path="model.pt")          # a file -> saved as an artifact
sp.log_result({"acc": 0.97, "f1": 0.95})              # several at once
```

By default a file given with `path=` is copied into the run's storage (`save_result=True`); pass
`save_result=False` to record only a pointer to the file in place.

## Figures (with data provenance)

Log a matplotlib figure and record *what data produced it* — the key feature for answering
"which run/data made this plot?" months later:

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot(x, np.polyval(coef, x))
sp.log_figure(fig, name="fit", used=["coef"], caption="Linear fit")
```

`used=` lists the parameter/result names the figure was built from. You can also log an
already-saved image with `path="figure.png"`.

## Metadata, tags, and notes

```python
sp.add_metadata("dataset", "mnist")          # or a dict
sp.add_tag("baseline")                         # or a list of tags
sp.add_note("first attempt with the new solver")
```

These are all stored in the database and are cheap to [query](analysis.md) later.

## Tracking a function

The `@sp.track` decorator logs a function's arguments, duration, and return value automatically:

```python
@sp.track(run_name="sweep", save_result=True)
def run_experiment(lr, epochs):
    ...
    return final_loss
```

## Finishing a run

A run is finalized (runtime, status, source committed, data flushed) automatically when your
script exits. To finalize early — e.g. to log several runs in one script — call:

```python
from sillonpy.api import force_dump
force_dump()
```

See the [`sillonpy` API reference](../reference/sillonpy.md) for full signatures.
