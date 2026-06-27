# Analysis

`sillonlab` loads a project's logged runs into Python — in a script or a notebook — so you can
explore, query, and post-process them. It reads the same `.sillon/` store your runs were logged
to; nothing needs to be running.

```python
import sillonlab as sl

project = sl.load_project()            # current directory, or load_project("path/to/project")
project.show()                          # pretty overview of every run
```

## Getting runs

```python
run = project.get("my_fit")            # one run, by name or uuid
runs = project.runs()                   # a RunCollection of all runs
run.show()                              # detail card: params, results (+sizes), figures, notes
```

## Reading a run

Lightweight fields are plain attributes; heavy values are loaded on demand (from HDF5/artifacts):

```python
run.parameters          # {"learning_rate": 0.01, ...}
run.results             # names of results + artifacts
run.tags, run.notes, run.metadata, run.status, run.runtime

run.load_result("coef")          # array read back from the glob
run.load_parameter("grid")       # big-array param read back from the glob
run.load_figure("fit")           # path to the figure file
run.load_source()                # the script that produced the run
run.fetch_result("coef", "out/") # copy a result/artifact/figure to disk
run.sizes()                      # storage footprint per stored item
```

## Querying

`project.query(...)` finds runs by any combination of criteria (all combined with AND). Cheap
filters (parameters, metadata, tags, date, status) are resolved straight from the database; result
and analysis **value predicates** read the glob, but only for the runs that already passed the
cheap filters.

```python
# parameters: equality (bare kwargs) or predicates
project.query(optimizer="adam")
project.query(learning_rate=lambda lr: lr < 0.1)

# metadata, tags, status, date
project.query(metadata={"dataset": "mnist"})
project.query(tags="baseline")
project.query(fields={"status": "SUCCESS"}, after="2026-06-01")

# presence
project.query(has_result="coef", has_analysis="fit_rmse")

# result / analysis value predicates (these read the glob)
project.query(results={"final_loss": lambda v: v < 0.05})
project.query(analyses={"fit_rmse": lambda v: v < 1e-3})

# combine freely — cheap filters run first, so this only opens the prod runs' globs
project.query(tags="prod", optimizer="adam", results={"loss": lambda v: v < 0.1})
```

`RunCollection.where(...)` takes the exact same arguments to filter an already-loaded collection:

```python
runs.where(optimizer="adam").where(results={"loss": lambda v: v < 0.1})
```

## Tables

```python
project.runs().to_dataframe()                       # one row per run, a column per parameter
project.query(tags="prod").to_dataframe(metadata=True, results=True)
```

## Annotating and post-processing

You can write back to finished runs — add notes/tags/metadata, or attach **analyses**:
derived data you compute later and want to keep with the run.

```python
run.add_note("kept for the paper")
run.add_tag("reviewed")
run.add_metadata("reviewer", "alice")

# attach post-processed data, then reload it anytime
import numpy as np
run.add_analysis("fit_on_grid", np.polyval(run.load_result("coef"), np.linspace(0, 1, 50)),
                 comment="evaluated on a fine grid")
run.load_analysis("fit_on_grid")
```

## Exporting and reporting

```python
run.export("my_fit.npz")                 # results + analyses as npz / npy / hdf5
run.report("my_fit_report.zip", with_data=True)   # manifest + readable report + source (+ data)
run.manifest()                           # the same report as a dict
```

## Comparing and deleting

```python
project.compare("my_fit", "my_fit_2")    # parameter + source diff
run.delete()                             # remove a run (data + database row) — irreversible
```

See the [`sillonlab` API reference](../reference/sillonlab.md) for the full surface.
