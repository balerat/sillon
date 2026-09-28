# Recipes

Things sillon does that are easy to miss, organised by the question rather than
by the command. Every snippet here was run against a real project.

---

## Finding things

### "Where are all my projects?"

```bash
sillon projects
```

The one command that works from **any** directory — it exists precisely because
you do not remember where the project is. `--prune` forgets ones whose folder is
gone.

```python
sl.open_project("Shaking Lattice")    # by name, a unique prefix is enough
```

### "Which runs used degree 3?"

```bash
sillon query -p degree=3
sillon query -p degree=3 solver=lstsq -t baseline --status SUCCESS
sillon query --after 2026-01-01 --limit 20
```

Values are parsed as Python literals, so `-p lr=0.01` compares as a float, not a
string.

### "Did I already do something like this?"

```bash
sillon like fit_d2
```

Ranked by how much of the configuration two runs share, with a tiebreak on how
far the differing values moved.

### "Which run produced this file?"

```bash
sillon trace figures/fit.png
sillon trace 9f2c8a1e…            # or a bare SHA-256
```

Works on **artifacts and figures** — files sillon copied into the store. It will
*not* match a file produced by `sillon fetch` or `run.export()`, because those
re-serialise the data and so hash differently from the original.

---

## Getting data out

### "I just want this one array as a file"

```bash
sillon fetch fit_d1 -r coef
sillon fetch fit_d1 -r coef --dest out/
```

```python
run.fetch("coef", dest="out/")
```

### "Give me everything this run produced"

```python
run.export("out/", format="npz")     # one compressed file
run.export("out/", format="npy")     # a folder, one file per result
run.export("out/", format="hdf5")    # results + parameters as attributes
```

### "Something I can archive or send to someone"

```bash
sillon report fit_d1 --dest out/
sillon report fit_d1 --dest out/ --with-data
```

A zip holding `manifest.json`, a human-readable `report.md`, and
`source/main.py` — the script that produced the run. `--with-data` adds
`data.hdf5` with the results themselves.

Like `grab`, `--dest out/` means *inside* that folder; give a filename to
control the name.

### "What is in this run, and how big is it?"

```python
run.manifest()    # every parameter, result, artifact, figure, analysis
run.sizes()       # bytes per stored dataset
```

Useful before pruning: `sizes()` tells you which runs are actually costing you
disk.

---

## Annotating and tidying

### "Let me label this for later"

```bash
sillon add fit_d1 -n "used in figure 3" -t publication reviewed
sillon add run_a run_b -t sweep          # several runs at once
```

```python
run.add_note("used in figure 3")
run.add_tag("publication")
run.add_metadata("reviewed_by", "AL")
```

### "This name is meaningless"

```bash
sillon rename infallible_hoover cubic_fit
```

Auto-generated names are fine while sweeping and terrible six months later.
Renaming is safe — lineage edges are keyed by uuid, not by name.

### "I need the disk space back"

```bash
sillon prune --older-than 90d
sillon prune --run-id fit_d1 fit_d2
sillon prune --older-than 90d --delete-metadata
```

By default prune deletes the **stored data** and keeps the database row, so the
record of what you ran survives — you still know the parameters, you just no
longer have the arrays. `--delete-metadata` removes the rows too, and that is
the only form that prompts, because it is the irreversible one.

Prune refuses to run without a scope: you must give `--run-id` or
`--older-than`.

### "Delete this run entirely"

```bash
sillon delete fit_d1          # prompts
sillon delete fit_d1 -y       # does not
```

Removes the row **and** the stored data.

---

## Understanding what happened

### "What changed between these two?"

```bash
sillon diff fit_a fit_b
sillon diff fit_a fit_b --source      # + the unified source diff
```

Read the `Code` line first — it tells you whether the comparison was fair at
all. See [Code versions](code-versions.md).

### "What was this sweep even varying?"

```bash
sillon diff --across tag=sweep
```

```text
  varying   degree: 1, 2, 3, 4, 5
  varying   ridge: 0.0, 0.1
  constant  seed, solver
  code      one version (98167c00)
```

The question you have when you return to a folder of runs whose names mean
nothing to you.

### "Where did this run come from?"

```bash
sillon lineage refined
```

```python
run.parent_links()    # [{"uuid", "name", "relation", "items"}]
run.parents()         # walkable Run handles
run.children()        # runs derived from this one
```

`relation` is `read` when sillon inferred the link from data you loaded, and
`derived-from` when you declared it with `inherit=`.

### "Show me everything about this run"

```bash
sillon show fit_d1 -p -r -t -n      # parameters, results, tags, notes
sillon show fit_d1 -m %all%         # all metadata, including what sillon recorded
sillon show fit_d1 -f               # figures, with what drew them
sillon show fit_d1 -A               # analyses, with what they were computed from
```

```python
run.load_source()     # the script that produced it, as logged
```

`load_source()` is the one people forget: the entry script is stored with every
run, so a run stays readable after you have edited the file that made it.

---

## Working in a notebook

### "Rank these and plot the best"

```python
best = project.query(has_tag="sweep").sort_by("rmse")[:5]
best.to_dataframe()
```

### "Keep this derived quantity with the run"

```python
spectrum = np.fft.rfft(run.load_result("field"))
run.add_analysis("spectrum", spectrum, used=["field"])
```

Stored beside the results and queryable the same way. Omit `used=` and sillon
infers it from what you loaded.

### "Stop attaching my browsing to the next run I log"

```python
sl.pending_reads()    # what would be recorded as parents right now
sl.forget_reads()     # clear it
```

Only *data* loads are recorded — listing runs and reading `.parameters` are not.
See [Provenance](provenance.md).

---

## Housekeeping you might not know about

### The daemon

```bash
ps aux | grep sillon-server-daemon
kill "$(cat .sillon/daemon.pid)"
```

One per project, started on the first log call, gone after five minutes idle.
`SILLON_IDLE_TIMEOUT` (seconds) changes that — raise it if you run scripts in
bursts and want it to stay warm.

### Logging somewhere other than the current folder

```python
with sp.track_run(project_path="/scratch/job-4821"):
    ...
```

### Sealing a run early

```python
sp.init(run_name="first")
...
sp.force_dump()          # sealed; a later init() starts a new run
```

`track_run` does this for you — prefer it unless your script is one run.

### Exercising the Windows code path on Linux or macOS

```bash
SILLON_TRANSPORT=tcp make test
```

The client and daemon talk over a Unix socket where one exists and a loopback
TCP port on Windows. This forces the latter, which is how the Windows path is
tested on CI.
