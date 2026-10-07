# Moving runs between machines

You run simulations on a laptop and a desktop, or on a cluster and then locally,
and the results end up in two places. A **bundle** is how you bring them
together: one file holding everything needed to reconstruct a set of runs
somewhere else.

```bash
# on the laptop
sillon export --dest /Volumes/share/

# on the desktop
sillon import /Volumes/share/Lattice~laptop~20261007T185407Z.sillon
```

That is the whole mechanism. There is no server, no sync daemon and nothing to
configure — a bundle is a file, so anything that moves files moves runs: a
shared drive, `scp`, Dropbox, a USB stick, an email attachment.

## A bundle is not a report

Sillon writes two kinds of archive and they are for different readers.

| | `sillon report` | `sillon export` |
|---|---|---|
| for | a person | another sillon |
| holds | a manifest and a readable `report.md` | every field, every byte |
| results | values under 512 bytes; the rest as a size | all of them |
| artifacts, figures | never | yes |
| heavy parameters | a marker | yes |
| code version, hashes | no | yes |
| can be read back | no | yes |

If you want to send someone a summary of a run, that is `report`. If you want
the run itself to exist somewhere else, that is `export`.

## What travels

Everything, by default:

- every parameter, including arrays offloaded to HDF5
- every result, whatever its size
- artifact and figure bytes, with the figures' `used=` provenance
- tags, notes, analyses
- the run's uuid, both timestamps, status, runtime, hostname and author
- the code version, and the source text behind it
- lineage edges

And the version of sillon that **wrote** the run, not the one importing it — so
`sillon query --status` and a `sillonversion` filter still tell you the truth
about where a run came from.

`--no-data` leaves the heavy data behind and carries only the records. The runs
arrive as **stubs**: they show up in `sillon list` and `query`, and reading
their data fails. Useful for "what did you run?" when the arrays are gigabytes
and you only want the index.

## Importing is union, never overwrite

An import adds what you do not have and touches nothing you do.

```bash
sillon import --dry-run bundle.sillon
```

```text
╭─ Would import ─────────────────────────────────────────────────╮
│                                                                │
│    from     Lattice  on  laptop   2h ago                       │
│    wrote by sillon 2.1.0   with data                           │
│                                                                │
│    new      3   already here  12                               │
│                                                                │
│     Run                                                        │
│   ───────────────────────────────────────────────────────────   │
│     deg5                                                       │
│     deg3~laptop            was deg3 — the name is taken here   │
│     deg6                                                       │
│                                                                │
╰────────────────────────────────────────────────────────────────╯
```

Because nothing is ever overwritten, **re-importing is safe and is the point**:
running `sillon import` on a bundle you have already read tells you whether
there is anything new in it, and does nothing if there is not.

### Why names get suffixed

A run's identity is its uuid, which has been globally unique since sillon
started minting them. A name is not an identity: two machines running the same
sweep will both produce a `deg3`, and neither knows about the other.

So when an incoming name is already taken, the **incoming** run is renamed to
`deg3~laptop` — tagged with where it came from — and your local `deg3` keeps
its name and its values. Nothing is hidden and nothing is merged.

This matters for lineage, and sillon handles it: a parent edge records both the
parent's uuid and the name it had at the time, and the edge is followed by
**uuid**. So a renamed parent still resolves to the right run:

```python
project.get("refined").parents()[0].name     # 'deg3~laptop'
project.get("refined").parents()[0].parameters["degree"]   # 3, not your local 99
```

### Lineage that points outside the bundle

Export a child without its parent and the edge survives, because it is still a
true statement about where the run came from — but it cannot be walked. The
import says so:

```text
  lineage  refined's parent deg3 was not imported — the edge is kept
```

Walking it later gives a clear error rather than a mystery:

```text
Run 'deg3' (aaaaaaaa-...) is not in this project.
A lineage edge can point at a run that was never imported.
```

## From Python

Both surfaces share the same engine, as everywhere else in sillon.

```python
import sillonlab as sl

project = sl.load_project()

project.export(dest="/Volumes/share/")           # everything
project.export(tags="sweep", dest="sweep.sillon")
project.export(["deg3"], with_data=False)

project.import_bundle("sweep.sillon", dry_run=True)
project.import_bundle("sweep.sillon")
```

## What a bundle looks like inside

A zip, whose layout deliberately mirrors sillon's own on-disk layout:

```text
sillon-bundle.json              what this is and where it came from
runs/<run-uuid>/
  run.json                      the run row and its child rows
  glob/glob.hdf5                copied verbatim
  artifact/<artifact-uuid>/...  copied verbatim
  figure/<figure-uuid>/...      copied verbatim
sources/<sha256>                the code behind the included runs
```

The mirroring is what makes importing cheap and safe: a whole `<run-uuid>/`
tree moves with every pointer inside it still valid, because artifact and
figure rows store a **uuid folder name** rather than a filesystem path. No HDF5
dataset surgery happens, and the inner folders are never merged.

`sources/` merges by union without any bookkeeping, because it is
content-addressed — a blob already present cannot differ, since its name is the
hash of its contents.

A bundle records the format version it was written with, and a sillon that does
not understand it refuses to read it rather than importing half of it.

## Limits worth knowing

- **Content-hash matching across machines is unreliable.** `sillon trace`
  identifies a file by hashing it, and for values that were never files the hash
  comes from `pickle.dumps`, whose output is not guaranteed stable across Python
  versions. Importing is unaffected — it dedups on uuid — but do not expect
  `trace` to recognise a figure produced from the same data on a different
  Python.
- **`started_at` for old runs is inferred.** Runs logged before sillon recorded
  an offset get one derived from their local-time string, assuming they were
  logged on the machine reading them. Imported runs carry a real one.
- **A shared drive is a place to put bundles, not a project to open.** Pointing
  two machines at one `.sillon/` on SMB or NFS is not supported and not safe:
  WAL locking is unreliable there, and the two daemons would fight over the
  same endpoint files.
