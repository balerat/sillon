# Troubleshooting

## First place to look

Your script talks to a background daemon. When something is wrong, the daemon's
log usually says why:

```bash
tail -50 .sillon/daemon.log
```

## Common messages

### `No active sillon run. Call sillonpy.init() first...`

You logged before opening a run.

```python
sp.log_param("x", 1)          # no run open

with sp.track_run():          # fix
    sp.log_param("x", 1)
```

### `Not in a sillon project.`

You are not inside one. The CLI searches **upward** for a `.sillon/` directory,
so being in a subdirectory is fine — this means no ancestor has one either.
Either find the project you meant, or make this one:

```bash
sillon projects
```

```bash
sillon init --name "My Project"
```

(`sillon projects` and `sillon init` are the two commands that work from
anywhere.)

### `Cannot open this project: No sillon database found ...`

The project directory is there but its database is not — usually a storage root
on a disk that is not mounted, or a partial copy. This is what `check` is for,
and it is the one command that still runs:

```bash
sillon check
```

```text
  broken     the project's database could not be opened, so its runs could not be checked
  broken     the recorded storage root is not there: /Volumes/bigdisk/sillon
```

### `Run '<name>' (<uuid>) is not in this project.`

A lineage edge pointing at a run that is not here — normally a child imported
without its parent. The edge is kept deliberately, because it is still a true
statement about where the run came from; it just cannot be walked. Import the
rest of the source, or leave it. `sillon check` lists them all.

### `Daemon failed to start. Check logs at .../daemon.log`

The daemon could not come up. The log names the cause. Most common:

- **`AF_UNIX path too long`** (Linux/macOS only) — the socket path has a hard OS
  limit of about 104 characters, and it lives inside your project. A deeply
  nested project directory hits it. Move the project somewhere shallower, or
  point the run elsewhere with `project_path=`. Windows uses a loopback TCP
  port instead and has no such limit.
- An import error in your environment — the daemon runs on the same interpreter
  as your script.

### `Result '<name>' ... is recorded in the database but missing from the run's HDF5 store`

The run's row survived but its array store did not — a pruned run, an
`import --no-data`, or a partially copied `.sillon/`. The value is genuinely
gone; the error is telling you rather than handing back a placeholder.
`sillon check` lists every run in this state.

### `TypeError: Object of type X is not JSON serializable`

You logged a custom object. Convert it first — a dict, a list, a string, or a
numpy array all work.

### A command failed and my script stopped

That is intentional. A failed log call raises rather than continuing, because a
run that silently drops a value is a run that lies about what it contains. The
message names the command that failed; `.sillon/daemon.log` has the traceback.

## Run status

| Status | Meaning |
|---|---|
| `SUCCESS` | the script finished normally |
| `CRASHED` | it raised an uncaught exception, or the process was killed |
| `RUNNING` | still in flight, or the daemon died before it could be sealed |

A crashed run records why:

```bash
sillon show my_run -m %all% | grep error
```

```text
sillon.error.type      RuntimeError
sillon.error.message   the simulation blew up
```

A run stuck at `RUNNING` long after the script ended means the daemon was killed
mid-commit. The data logged before that point is in the store; the row was
never finalised.

## The daemon

```bash
ps aux | grep sillon-server-daemon
```

- **One per project**, started on the first log call.
- **Exits after five minutes idle.** Override with `SILLON_IDLE_TIMEOUT`
  (seconds) — raise it if you run scripts in bursts and want it to stay warm.
- It will not exit while a run is still open.

Its endpoint files live in `.sillon/` and are removed when it exits:
`daemon.sock` on Linux/macOS, or `daemon.port` and `daemon.token` on Windows.

To stop one by hand:

```bash
kill "$(cat .sillon/daemon.pid)"          # Linux/macOS
taskkill /PID (Get-Content .sillon\daemon.pid) /F   # Windows PowerShell
```

Killing it while a run is open loses that run's unsealed data. Killing it
between runs is harmless.

## Starting over

A project is just a directory:

```bash
rm -rf .sillon/          # deletes every run in the project
```

To remove individual runs and reclaim space instead:

```bash
sillon delete my_run
sillon prune --older-than 30d
```

## Upgrading sillon

Databases from older versions are migrated in place the first time a newer
sillon opens them — new columns and indexes are added automatically, and no run
is rewritten. **Back up `.sillon/` before upgrading anyway** if the project
matters; a migration is still a change to a file full of results.

## Reporting a bug

Include:

- `sillon --version`, your Python version and OS
- the relevant part of `.sillon/daemon.log`
- the smallest script that reproduces it

[github.com/balerat/sillon/issues](https://github.com/balerat/sillon/issues)
