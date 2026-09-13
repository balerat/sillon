# 02 — Parameter sweep

Ten runs from one script, then ranking them.

```bash
python run.py       # logs 10 runs
python analyse.py   # finds the best three
```

Points of interest:

- **`track_run` in a loop.** Each iteration is its own run, sealed on exit. A
  crash mid-sweep costs you one run, not the whole batch — and that run is
  recorded as `CRASHED`, not silently as a success.
- **No run names.** Omit `run_name` and sillon generates one, guaranteed unique
  within the project.
- **Two-phase queries.** `project.query(...)` filters on the database first and
  only touches the HDF5 store for runs that survive, so filtering on a parameter
  stays fast even when the results are large.
- **`sort_by`** takes a parameter or result name, or a callable, and returns a
  collection you can slice.
