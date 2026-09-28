# Provenance and lineage

The part of sillon that answers questions you will have *later*: where did this
figure come from, what did this run derive from, which run produced this file.

## Which data drew this figure?

Record it when you log the plot:

```python
sp.log_figure(fig, name="fit", used=["coef", "degree"],
              caption="Linear fit over the noisy sample")
```

`used=` names the logged values the figure was built from. Months later:

```bash
sillon show my_fit -f
```

```text
fit  ← built from: coef, degree
```

```python
run.figures        # {'fit': {'used': ['coef', 'degree'], 'caption': ...}}
```

This costs one argument at logging time and is the difference between a figure
you can defend and one you have to reproduce from memory.

## Which run derives from which?

Usually you do not have to say. If your script loads an earlier run's data
through sillonlab and then logs a new run, sillon saw that happen and records
the link itself:

```python
import sillonlab as sl, sillonpy as sp

prev  = sl.load_project().get("equilibrated")
state = prev.load_result("final_state")        # ← sillon notices this

with sp.track_run(project_name="dynamics"):
    sp.log_result("trajectory", evolve(state))
    # parent edge to `equilibrated` recorded, naming `final_state`
```

No annotation, no discipline required. The edge records **which items** you read,
so you can see not just *that* one run fed another but *what* passed between them.

### What counts as deriving

Only loading a run's **data** — `load_result`, `load_parameter`, `load_analysis`,
`load_artifact`, `load_figure`. Browsing does not: listing runs, reading
`.parameters`, calling `.show()` or `to_dataframe()` records nothing, because
looking at a run is not deriving from it.

In a long exploratory session where earlier reads should not attach themselves
to the next run you log:

```python
sl.pending_reads()    # what would be recorded right now
sl.forget_reads()     # start the provenance clean
```

!!! warning "Same process only"
    The link is made by watching one process do both halves. Load data in a
    notebook, write it to a file, then run a separate script, and there is no
    edge — nothing observed the connection. Use `inherit=` when the two halves
    genuinely happen in different processes.

### Declaring it explicitly

```python
with sp.track_run(run_name="refined", inherit="baseline"):
    sp.log_param("degree", 3)
```

`inherit` takes a run name, a uuid, or a `sillonlab.Run`. **Nothing is copied** —
it records an edge. The child logs its own parameters; the link lets you walk
back.

Edges carry a `relation` so the two kinds stay distinguishable: `derived-from`
for something you declared, `read` for something sillon inferred. Declaring a
run you also read gives one merged edge, not two.

```bash
sillon lineage refined
```

```text
╭─ lineage · refined ─╮
│  run  refined       │
│                     │
│  Inherited from     │
│    ↑ baseline       │
│  Used by            │
│    (none)           │
╰─────────────────────╯
```

```python
run.parent_links()       # [{'uuid': ..., 'name': 'baseline'}]
run.parents()            # a RunCollection
run.children()           # runs that inherited from this one
```

The parent must already exist; `inherit` raises if it does not, rather than
recording a dangling edge.

## Code versions

The question this answers: *"I fixed a sign error in September — which of my 135
runs used the fixed code?"*

Every run records a hash of the code that produced it. Not a hash of the text —
that would report a new version every time you tuned a constant or added a
comment, which makes it useless. Instead the code is parsed and hashed
**structurally**, with literal values normalised away:

| Change | New version? |
|---|---|
| `N = 5` → `N = 4` | no |
| a comment, a reformat | no |
| `kinetic - potential` → `kinetic + potential` | **yes** |
| a changed function in your own library | **yes** |

### It covers your own modules, not just the script

A run's version spans the entry script **and** every module of yours that was
imported. Editing your own library counts as a code change, which is usually
where the change actually is.

Third-party libraries and sillon itself are excluded — only your code.

```bash
$ sillon versions
  2 code versions across this project

  Version    Runs   First seen   Last seen   Constants   Covers
  f10236bb     72   Aug 02       Aug 24          3       all code
  744e82d9     63   Aug 25       Sep 28          —       all code
```

`Constants` says how many literal-level variants share that logic — runs that
differ only by a value you tuned.

Then drill into one, and see which file moved:

```bash
$ sillon versions 744e82d9
  File                Logic      Exact
  run.py              cf6d74aa   46a8ba01
  lattice/ham.py      f220bf39   ffc5a3e8
```

### Filtering by version

```python
clean = project.query(fields={"logic_version": "744e82d9..."})
```

### Older runs

Runs logged before this feature have no version, but they did record their entry
script, so it can be recovered:

```bash
sillon versions --backfill
```

Those cover the **entry script only** — nobody stored your modules back then —
and are labelled that way so they are never mistaken for a full version.

### What it cannot see

Modules imported lazily *inside a function* after the run starts are not
included: the module list is taken when the run opens. Top-level imports, which
is nearly everything, are covered.

## Which run produced this file?

Every logged value and file is hashed. Given a file on disk:

```bash
sillon whose figures/fit.png
```

It hashes the file and finds the run that produced it. Works with a bare hash
too, and from Python:

```python
project.find_by_hash("figures/fit.png")
```

## What changed between two runs?

```bash
sillon compare baseline refined
```

```python
project.compare("baseline", "refined")
```

Reports differing parameters, metadata, and whether the source code changed.

## What exactly is in a run?

```python
run.manifest()      # every parameter, result, artifact, figure, analysis
run.sizes()         # bytes per stored dataset
run.load_source()   # the script that produced it, as logged
```

The source of your main script is captured on every run, so a run remains
readable even after you have edited the file that produced it.
