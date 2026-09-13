<h1 align="center">sillon</h1>

<p align="center">
  <strong>Git for simulations</strong> — log, track and query your simulation runs.
</p>

<p align="center">
  <a href="https://pypi.org/project/sillon/"><img alt="PyPI" src="https://img.shields.io/pypi/v/sillon"></a>
  <a href="https://pypi.org/project/sillon/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/sillon"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue"></a>
</p>

---

You ran the simulation four months ago. The figure is in the paper draft. Which
parameters produced it, and is the array it was plotted from still on disk?

sillon answers that. It records the parameters, results, figures, metadata and
source of every run into a local store, and gives you a CLI and a Python API to
query them afterwards. It is local-first, needs no server and no account, and is
built for people who run parameter sweeps rather than training loops.

```bash
pip install sillon
```

## Log a run

Three lines in a script you already have:

```python
import sillonpy as sp

with sp.track_run(run_name="my_fit", project_name="demo"):
    sp.log_param("degree", 1)                  # what you chose
    coef = np.polyfit(x, y, 1)
    sp.log_result("coef", coef)                # what came out
    sp.add_tag("baseline")
```

Run it normally. No setup step, no `sillon init` — the first call creates
`.sillon/` next to your script. Large arrays go to HDF5 automatically; runs are
never overwritten.

## Look at it

```bash
sillon context            # every run in the project
sillon show my_fit        # one run in detail
sillon projects           # every project on this machine, and where it is
```

```text
╭─ Project ──────────────────────────────────────────────────────╮
│  10 runs logged in the project                                 │
│                                                                │
│    ID          Run Name        When       Params  Assets  Status   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│    39629020    trusting_cannon just now     2       2    SUCCESS   │
│    7e7e5330    happy_perlman   just now     2       2    CRASHED   │
╰────────────────────────────────────────────────────────────────╯
```

## Query it

Plain Python — no query language:

```python
import sillonlab as sl

project = sl.load_project()

best = project.query(
    tags="sweep",
    parameters={"degree": lambda d: d <= 3},   # cheap: filtered in SQL
    results={"rmse": lambda v: v < 0.1},       # heavy: only on what survived
).sort_by("rmse")[:5]

print(best.to_dataframe())
```

## What makes it different

**The record is trustworthy.** A run that crashed is recorded as `CRASHED`, with
the exception type and message — never as a success. A log call that fails
raises instead of silently dropping your data.

**Figures remember their data.** `log_figure(fig, used=["coef", "degree"])`
records what drew the plot, so `sillon show -f` can tell you months later:

```text
fit  ← built from: coef, degree
```

**Runs remember their ancestry.** `track_run(inherit="baseline")` records a
lineage edge you can walk with `sillon lineage`, `run.parents()` and
`run.children()`.

**Files remember their run.** Everything is content-hashed, so
`sillon whose figures/fit.png` tells you which run produced a file you found.

**It stays out of the way.** Zero configuration, a background daemon you never
start, and heavy arrays offloaded without you thinking about it.

## Documentation

| | |
|---|---|
| [Quickstart](docs/getting-started/quickstart.md) | five minutes, end to end |
| [Core concepts](docs/getting-started/concepts.md) | the mental model — read once |
| [Logging runs](docs/guide/logging.md) | the whole logging API |
| [Querying and analysis](docs/guide/analysis.md) | working with many runs |
| [Provenance and lineage](docs/guide/provenance.md) | figures, ancestry, hashes |
| [CLI reference](docs/reference/cli.md) | every command |
| [Troubleshooting](docs/guide/troubleshooting.md) | when something breaks |

Runnable [examples](examples/): a quickstart, a parameter sweep, and figure
provenance.

## Requirements

Python 3.11+, Linux or macOS. Windows is not supported yet — the client and the
daemon talk over a Unix domain socket.

## How it works

Your script sends what it logs to a small per-project background daemon, which
writes to SQLite (light values, so filtering is fast) and HDF5 (heavy arrays).
The CLI and `sillonlab` both read through one engine, so they never disagree.
See [Architecture](docs/dev/architecture.md).

## Status and roadmap

The logging API, the daemon, the CLI and the analysis library are in daily use.

Not implemented yet, despite appearing in older notes: `sillon run`
(reproduction), `sillon watch`, `sillon estimate`, a GUI, Slurm integration, and
non-Python clients. If a command is not in the [CLI reference](docs/reference/cli.md),
it does not exist.

## Contributing

```bash
git clone https://github.com/balerat/sillon
cd sillon
pip install -e ".[dev]"
make test
```

See [Contributing](docs/dev/contributing.md) and
[Development setup](docs/dev/development.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
