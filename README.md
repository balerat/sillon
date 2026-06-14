# sillon

**Git for simulations** — log, track, and analyze your simulation runs.

sillon records the parameters, results, metadata, figures, and source code of every run into a
local store (SQLite + HDF5), then lets you explore and compare those runs from the command line
or from a notebook. It is designed for researchers who run many simulations and want to keep
track of what produced what.

> Status: pre-1.0. The Python logging API, the background server, the CLI, and the analysis
> library are functional. See the [roadmap](#roadmap) for what is not yet implemented.

## Install

```bash
make install        # editable install of all packages into the active environment
# or:
pip install -e ./packages/common/ -e ./packages/interface/cli \
            -e ./packages/interface/sillonlab -e ./packages/pyapi/ -e ./packages/core/
```

This provides two console commands: `sillon` (the CLI) and `sillon-server-daemon` (the logging
server, launched automatically by the Python API).

## Quickstart — logging a run

```python
import sillonpy as sp
import numpy as np

sp.init(run_name="my_fit", project_name="demo")   # starts/at­taches to the project store

x = np.linspace(0, 10, 100)
sp.log_param("degree", 1)
coef = np.polyfit(x, 1.3 * x + 5, 1)
sp.log_result("coef", coef)                        # heavy arrays go to HDF5 automatically

import matplotlib.pyplot as plt
fig, ax = plt.subplots(); ax.plot(x, np.polyval(coef, x))
sp.log_figure(fig, name="fit", used=["coef"], caption="Linear fit")  # figure + data provenance

sp.add_tag("baseline"); sp.add_note("first attempt")
```

Run your script normally (`python my_script.py`). A run is stored under `.sillon/`. Re-running
with the same `run_name` auto-increments it (`my_fit`, `my_fit_2`, ...), so nothing is overwritten.

## Quickstart — analyzing runs

```python
import sillonlab as sl

project = sl.load_project()          # defaults to the current directory
project.show()                       # pretty overview of all runs

run = project.get("my_fit")
run.show()                           # detail card: params, results (+sizes), figures, notes
coef = run.load_result("coef")       # read the array back from HDF5
project.query(degree=1, has_result="coef").to_dataframe()   # filter + tabulate

# attach post-processed data to an existing run for later reuse
run.add_analysis("fit_on_grid", np.polyval(coef, np.linspace(0, 1, 50)), comment="fine grid")

# bundle a run's full context (manifest + readable report + source) into a zip
run.report("my_fit_report.zip", with_data=True)
```

## CLI overview

Run from inside a project directory:

```bash
sillon context                       # overview of all runs
sillon search -p optimizer=adam -r coef   # find runs by parameter / result / artifact
sillon show my_fit -p -r             # detailed parameters and results
sillon compare my_fit my_fit_2       # parameter + source diff
sillon add my_fit --tag production --note "kept"
sillon grab my_fit -r coef --dest ./out      # fetch a result/artifact as a file
sillon report my_fit --with-data     # export a context bundle zip
sillon prune --older-than 30d        # free disk space (keeps metadata by default)
```

See [docs/cli.md](docs/cli.md) for the full reference.

## Packages

| Package | Role |
|---|---|
| `silloncommon` | Data layer: ORM models, queries, command protocol |
| `silloncore` | Engine (single source of truth), logging server, HDF5/glob storage |
| `sillonpy` | Python client API used inside simulation scripts |
| `silloncli` | The `sillon` command-line tool |
| `sillonlab` | Analysis library for scripts and notebooks |

## Testing

```bash
make test
```

## Roadmap

Not yet implemented: a GUI, a collaborative web platform, Slurm integration, run
reproduction/relaunch (`sillon run`), a live-monitoring TUI (`sillon watch`), resource
estimation (`sillon estimate`), and native client APIs for other languages.
