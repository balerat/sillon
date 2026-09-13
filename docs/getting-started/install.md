# Install

```bash
pip install sillon
```

That is the whole toolchain: the logging client, the CLI, and the analysis
library. There is no server to configure and no account to create.

## Optional extras

```bash
pip install "sillon[analysis]"   # + pandas, for to_dataframe()
```

Figures need `matplotlib`, which sillon does not install for you — if you are
plotting, you already have it.

## Requirements

- Python 3.11 or newer
- Linux, macOS or Windows

The client and the daemon talk over a Unix domain socket where one is available,
and over a loopback TCP port on Windows, where CPython does not expose
`AF_UNIX`. You do not configure this — sillon picks the right one. Set
`SILLON_TRANSPORT=unix|tcp` only if you want to force it (the test suite does,
to exercise the Windows path on Linux).

## Check it worked

```bash
sillon --version
```

You get two commands on your `PATH`:

| Command | What it is |
|---|---|
| `sillon` | the CLI you use to explore runs |
| `sillon-server-daemon` | the background logging daemon — **you never start this yourself** |

## What gets created, and where

Nothing until you log something. The first time a script calls `sillonpy`,
sillon creates a `.sillon/` folder next to it:

```
.sillon/
  database.sql            SQLite: one row per run
  glob/<uuid>/glob.hdf5   heavy arrays
  artifact/<uuid>/        files you logged
  figure/<uuid>/          figures you logged
  daemon.log              the background daemon's log
```

That folder *is* your project. Copy it, move it, back it up like any other data.

Add it to your `.gitignore` — it holds results, not source:

```gitignore
.sillon/
```

One file lives outside the project: a registry of every project on this machine,
so `sillon projects` can tell you where they all are. It goes in
`~/.config/sillon/` (or `%APPDATA%\sillon` on Windows).

## Install from source

```bash
git clone https://github.com/balerat/sillon
cd sillon
pip install -e ".[dev]"     # or: make install
make test
```

See [Development setup](../dev/development.md) for the layout of the repository.
