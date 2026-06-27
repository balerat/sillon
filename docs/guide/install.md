# Install

sillon is a single package on PyPI. It needs **Python ≥ 3.11**.

```bash
pip install sillon
```

The analysis library can produce pandas DataFrames; if you want that, install the optional
`analysis` extra (it just adds `pandas`):

```bash
pip install "sillon[analysis]"
```

## What you get

Installing `sillon` gives you everything in one shot:

- the **`sillonpy`** Python client you import in your simulation scripts,
- the **`sillonlab`** analysis library for scripts and notebooks,
- two console commands:
    - **`sillon`** — the command-line tool to explore your runs,
    - **`sillon-server-daemon`** — the background logging server (you never start this yourself;
      `sillonpy` launches it automatically the first time a script logs to a project).

Check it works:

```bash
sillon --help
```

## Where data lives

Each project keeps its data in a `.sillon/` directory created next to where you run your scripts:
the SQLite database, the HDF5 "glob" files (heavy results/arrays), and copied artifacts and
figures. You can point a different machine or notebook at that folder to analyze the runs later.
