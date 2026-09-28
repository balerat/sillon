# Code versions

*"I fixed a sign error in September. Which of my 135 runs used the fixed code?"*

Every run records a hash of the code that produced it. `sillon versions` turns
that into an answer.

## Why it is not a hash of the file

Hashing the source text would be useless here. You tune a constant, and every
run before and after looks like a different code version — so the tool cries
wolf on runs that are perfectly comparable, and you stop trusting it.

So the code is parsed and hashed **structurally**, at three levels:

| Level | Ignores | Answers |
|---|---|---|
| `source_hash` | nothing | byte-identical? |
| `ast_hash` | comments, formatting, blank lines | did anything real change? |
| `logic_hash` | the above **+ every literal value** | did the *logic* change? |

What that means in practice:

| Change | New version? |
|---|---|
| `N = 5` → `N = 4` | no — a tuned constant is not a code change |
| adding a comment, reformatting, a docstring edit | no |
| `kinetic - potential` → `kinetic + potential` | **yes** |
| renaming a function, adding a statement | **yes** |

## It covers your own library too

A run's version spans the entry script **and** every module of yours that was
imported — which is usually where the change actually is. Third-party packages
and sillon itself are excluded; only your code counts.

```
my-project/
  run.py            ← counted
  lattice/ham.py    ← counted
  lattice/io.py     ← counted
  (numpy, scipy)    ← not counted
```

## Listing them

```bash
$ sillon versions
  2 code versions across this project

  Version    Runs   First seen   Last seen   Constants   Covers
  f10236bb     72   Aug 02       Aug 24          3       all code
  744e82d9     63   Aug 25       Sep 28          —       all code
```

**Constants** counts the literal-level variants inside one logic version — runs
that differ only by a value you tuned. Three variants under one version means
you ran the same program with three different settings.

## Seeing which file moved

```bash
$ sillon versions 744e82d9
  File                Logic      Exact
  run.py              cf6d74aa   46a8ba01
  lattice/ham.py      f220bf39   ffc5a3e8
  lattice/io.py       90ac3d11   1b7e4402
```

Compare the `Logic` column against another version to find the one that changed.
`sillon diff` does that comparison for you:

```bash
$ sillon diff fit_a fit_b
Code  same logic f10236bb — constants differ in run.py
```

```bash
$ sillon diff fit_a fit_c --source
Code  logic changed — lattice/ham.py

--- lattice/ham.py @ fit_a
+++ lattice/ham.py @ fit_c
-    H = kinetic - potential
+    H = kinetic + potential
```

## Analysing only the runs you trust

```python
import sillonlab as sl

project = sl.load_project()
clean = project.query(fields={"logic_version": "744e82d9…"})
```

A common shape: find the current version, then restrict everything downstream
to it.

```python
versions = project.context()          # or: sillon versions
clean = project.query(fields={"logic_version": current})
best = clean.sort_by("rmse")[:5]
```

## Runs logged before this existed

They have no version, but they did record their entry script, so it can be
recovered:

```bash
sillon versions --backfill
```

Those cover the **entry script only** — nobody stored your modules back then —
and are shown as `entry script only` so they are never mistaken for a full
version. Runs logged from now on cover everything.

## What it cannot see

- **Lazy imports.** The module list is taken when the run opens, so a module
  imported *inside a function* later is missed. Top-level imports — nearly
  everything — are covered.
- **Data.** A code version says the program is the same; it says nothing about
  the inputs. That is what parameters are for.
- **Your environment.** Library versions are not part of the code version.
  `run.metadata` records the imported module list if you need to check.

## Related

- [Provenance and lineage](provenance.md) — how runs, figures and analyses
  record where their data came from.
- [`sillon versions`](../reference/cli.md#sillon-versions--group-runs-by-the-code-that-produced-them)
  and [`sillon diff`](../reference/cli.md#sillon-diff--what-differs-between-runs).
