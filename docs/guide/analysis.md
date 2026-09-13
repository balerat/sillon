# Querying and analysis

`sillonlab` is the notebook and script side of sillon: load a project, filter
its runs, read the data back.

```python
import sillonlab as sl
```

## Loading a project

```python
project = sl.load_project()             # the current directory
project = sl.load_project("~/work/sweep")
project = sl.open_project("Shaking Lattice")   # by registered name
```

`open_project` accepts a name from `sl.list_projects()` (a unique prefix is
enough), so you do not have to remember paths. See [Projects](projects.md).

## Looking around

```python
project.show()                  # the overview table, same as `sillon context`
project.runs()                  # a RunCollection of every run
project.runs().list()           # just the names
run = project.get("my_fit")     # one run, by name, uuid, or uuid prefix
```

In Jupyter, a project, a run and a collection all render as tables.

## Querying

`project.query()` filters with plain Python. There is no query language to
learn: pass a value to match it, or a callable to test it.

```python
# exact matches
project.query(degree=3)
project.query(tags="baseline", fields={"status": "SUCCESS"})

# predicates
project.query(parameters={"degree": lambda d: d > 2})
project.query(results={"rmse": lambda v: v < 0.1})

# presence
project.query(has_result="coef", has_artifact="mesh", has_tag="gpu")

# time
project.query(after="2026-01-01", before="2026-06-30")
```

Filters combine with AND:

```python
best = project.query(
    tags="sweep",
    parameters={"ridge": lambda r: r == 0.0},
    results={"rmse": lambda v: v < 5.0},
)
```

!!! tip "Put cheap filters first"
    Filters on parameters, tags, status and dates are answered from the
    database. Filters on `results` and `analyses` have to open the HDF5 store,
    and run **only** on what the cheap filters left. Narrowing on a parameter
    before filtering on a result is what keeps a large project fast.

## Working with a collection

`query()` and `runs()` return a `RunCollection`:

```python
runs = project.query(tags="sweep")

len(runs)                       # how many
runs[0]                         # by position
runs["my_fit"]                  # by name or uuid
runs[:5]                        # a slice, still a RunCollection
for run in runs: ...            # iterate

runs.sort_by("rmse")            # by a parameter or result name
runs.sort_by("rmse", reverse=True)
runs.sort_by(lambda r: r.runtime)

runs.filter(lambda r: "gpu" in r.tags)
runs.where(has_result="coef")   # further narrowing, chainable

runs.show()                     # print a table
runs.to_dataframe()             # pandas
```

The common question, in one line:

```python
best_five = project.query(tags="sweep").sort_by("rmse")[:5]
```

Runs missing the sort key sort last, in both directions, so a partially-logged
run never displaces a real result.

## Reading a run

```python
run = project.get("my_fit")

run.parameters      # {'degree': 1}
run.results         # names of the logged results
run.metadata
run.tags
run.notes
run.runtime

coef = run.load_result("coef")       # arrays come back from HDF5
run.load_parameter("grid")
run.load_metadata("sillon.python.cwd")
run.load_source()                    # the script that produced the run
```

Files:

```python
run.load_artifact("mesh")            # path inside the store
run.load_figure("fit")
run.fetch_result("coef", dest="out/") # copy it out to your own directory
```

Asking for something a run does not have raises `LookupError` naming the run —
it never silently returns a placeholder.

## DataFrames

```python
df = project.query(tags="sweep").to_dataframe()
df = project.runs().to_dataframe(metadata=True, results=True)
```

One row per run; columns for name, timestamp, status, runtime, and every
parameter. `results=True` reads the array store, so it is slower — ask for it
when you want it.

Needs pandas: `pip install "sillon[analysis]"`.

## Annotating after the fact

```python
run.add_tag("publication")
run.add_note("Used in figure 3")
run.add_metadata("reviewed_by", "AL")
```

## Storing derived data

Computed something from a run and want it kept with the run?

```python
spectrum = np.fft.rfft(run.load_result("field"))
run.add_analysis("spectrum", spectrum, method="rfft")

run.load_analysis("spectrum")
```

Analyses live beside results in the store and are queryable the same way
(`project.query(analyses={"spectrum": ...})`).

## Exporting

```python
run.export("out/", format="npz")     # npz, npy or hdf5
run.report("out/")                   # a self-contained bundle
run.manifest()                       # what the run holds
run.sizes()                          # how much space it takes
```

## Housekeeping

```python
project.rename(run, "better_name")
project.delete_run(run)              # removes the row and its stored data
project.compare("run_a", "run_b")    # what differs between two runs
project.find_by_hash("out/fig.png")  # which run produced this file
```
