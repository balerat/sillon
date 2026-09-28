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
project.show()                  # the overview table, same as `sillon list`
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
run.fetch("coef", dest="out/") # copy it out to your own directory
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

## Provenance while you explore

Loading a run's data records it, so that a run you log later in the same process
is linked to it automatically — see [Provenance](provenance.md). Browsing is not
recorded; only actual data loads are.

```python
sl.pending_reads()    # runs whose data this session has read
sl.forget_reads()     # forget them, so they do not attach to your next run
```

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
run.add_analysis("spectrum", spectrum, used=["field"], method="rfft")

run.load_analysis("spectrum")
run.analyses["spectrum"]["used"]     # ['field']
```

`used=` records which of the run's values the analysis came from, so a derived
quantity keeps its origin. Omit it and sillon infers it from what you loaded —
see [Provenance](provenance.md).

Analyses live beside results in the store and are queryable the same way
(`project.query(analyses={"spectrum": ...})`).

## Finding similar runs

```python
for match in project.like("happy_perlman"):
    print(f"{match['score']:.0%}", match["name"], match["changes"])
```

```text
75% d2_r0.0 {'degree': (3, 2)}
75% d4_r0.0 {'degree': (3, 4)}
50% d2_r0.1 {'degree': (3, 2), 'ridge': (0.0, 0.1)}
```

Ranked by shared configuration, with a tiebreak on how far the differing values
moved. `same_code` on each match tells you whether the two runs were produced by
the same code version.

## Exporting

```python
run.export("out/", format="npz")     # npz, npy or hdf5
run.report("out/")                   # a self-contained bundle
run.manifest()                       # what the run holds
run.sizes()                          # how much space it takes
```

## Comparing runs

```python
d = project.diff("baseline", "refined")

d["code"]["same_logic"]                 # was this a fair comparison at all?
d["parameters"]["changed"]["degree"]    # {"old": 3, "new": 5, "delta_pct": 66.67}
d["results"]["rmse"]["delta_pct"]       # -37.11
d["results"]["coef"]["reason"]          # "shape"
```

Results are compared by **shape, dtype and hash**, never element by element, so
this stays fast on large arrays. Anything above `max_bytes` (64 MB by default)
is compared by shape and dtype alone and reported as `status="unknown"` rather
than silently guessed at.

The `code` block is the one to read first: it says whether the two runs differ
in *logic* or only in a tuned constant, which decides whether the rest of the
diff means anything.

For a whole sweep:

```python
across = project.diff_across(has_tag="sweep")
across["varying"]         # {"degree": [1,2,3,4,5], "ridge": [0.0, 0.1]}
across["constant"]        # {"seed": 7, "solver": "lstsq"}
across["logic_versions"]  # more than one means they are not all comparable
```

## Code versions and pruning from a notebook

```python
for group in project.versions():
    print(group["logic_version"][:8], group["run_count"], group["last_seen"])

current = project.versions()[0]["logic_version"]
clean = project.query(fields={"logic_version": current})
```

```python
project.prune(before="90d")                      # free the data, keep the record
project.prune(run_names=["old_run"], keep_metadata=False)   # remove it entirely
```

Both mirror `sillon versions` and `sillon prune` — see
[Code versions](code-versions.md).

## Housekeeping

```python
project.rename(run, "better_name")
project.delete_run(run)              # removes the row and its stored data
project.diff("run_a", "run_b")       # what differs between two runs
project.diff_across(has_tag="sweep") # what varies across a set
project.trace("out/fig.png")  # which run produced this file
```
