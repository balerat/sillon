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

```python
with sp.track_run(run_name="refined", inherit="baseline"):
    sp.log_param("degree", 3)
```

`inherit` takes a run name, a uuid, or a `sillonlab.Run`. **Nothing is copied** —
it records an edge. The child logs its own parameters; the link lets you walk
back.

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
