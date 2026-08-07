# Sillon — assessment and roadmap to a bedrock

## Context

You use sillon daily for logging + querying and find it handy; the lineage/diff engine is
deferred; you have large ambitions. You asked for an honest assessment and a shaped path
forward across performance, ergonomics, usage and usability.

Constraints you set: **audience = your lab / collaborators**; **one writer per project**
(concurrent workers, same machine; multi-*reader* is fine and wanted); **each user gets
their own project, even on a cluster**; WAL already planned; cross-host is a future
interest. And the daemon stays, because its future job is a **live console of all running
processes** — every run must transit a single daemon for that to work.

This document is the result of three audits (robustness, performance, ergonomics) plus
direct verification of every load-bearing claim below.

---

## Verdict

**Design instincts: excellent. Implementation robustness: not yet trustworthy. Release
process: the weakest link.**

Sillon has a real thesis and several genuinely differentiated ideas that nobody else in
this space executes well. It is also, right now, a tool that will quietly tell you a run
succeeded when it crashed, silently drop results without an error, and — at the version
currently tagged and released — cannot start its own daemon at all.

That gap is the whole story. You are not far from a bedrock, but the distance is not
measured in features. It is measured in **whether the record can be trusted**, and that is
the one property a lab notebook cannot compromise on.

---

## Part 1 — What is genuinely good (protect this)

Not filler. These are things the established tools get wrong:

1. **Zero-config onboarding.** `import sillonpy as sp; sp.init(); sp.log_param("x", 1)`.
   No tracking URI, no config file, no server to start, no `sillon init`. MLflow cannot do
   this. It is the correct design and it is why the daemon-spawn bug stings so much.
2. **Lambda predicates in `query()`** — `project.query(results={"loss": lambda v: v < 0.05})`
   with documented cheap-DB-filters-before-expensive-glob-reads ([project.py:140-184](packages/interface/sillonlab/src/sillonlab/project.py)).
   This beats MLflow's stringly-typed `filter_string` DSL outright. No parser, no escaping,
   arbitrary logic.
3. **Figure provenance** — `log_figure(fig, used=["coef"])` rendering as `fit ← built from: coef`.
   This directly answers "which data made this plot?", the actual pain of writing up six
   months later. Implemented end-to-end. **This is your most differentiated feature and
   nobody else has it.**
4. **Content-hashing every value** ([glob.py:11-32](packages/core/src/silloncore/glob.py)).
   This is the actual "git" in "git for simulations" and it is the foundation the lineage
   engine will stand on.
5. **Transparent heavy-array offload** — the user writes `log_result("field", big_array)`
   and never thinks about HDF5.
6. **One display layer for CLI and notebook** ([display.py](packages/core/src/silloncore/display.py)),
   with `_repr_html_` on `Run`/`RunCollection`. Consistency across surfaces for free.
7. **The engine returns pure data**; every CLI handler is a thin renderer over it. This is
   why the CLI and sillonlab stay in sync — and why `--json` would be nearly free.
8. **Careful destructive-op UX** — `prune` refuses to run unbounded, and its `--delete-metadata`
   prompt names the specific danger.

---

## Part 2 — The situation, in priority order

### P0 — `main` and the released v1.3.0 cannot spawn a daemon

[daemon.py:58 and :61](packages/pyapi/src/sillonpy/daemon.py). Two independent fatal bugs
in four lines, both from commit `1b66af9 "added some log"` — two commits before `49e67d2
Release v1.3.0`:

```python
cmd = [sys.executable, "-m", "-u", "silloncore.server.main", project_path]   # -u parsed as the module name
log_file.write(f"...[spawn] {datetime.now().isoformat()} ")                   # `import datetime` → module has no .now()
```

Verified end-to-end: a fresh project dies with `AttributeError: module 'datetime' has no
attribute 'now'` before `Popen` is reached. **A new user cannot log a single run.**

The process finding matters more than the bug: **the test suite catches this** (I ran it:
`4 failed, 7 errors`), and `.github/workflows/test.yml` runs those tests on every push to
`main`. So CI is red and was ignored, or the release didn't gate on it. For a tool whose
pitch is trustworthiness, shipping a non-functional release is the reputational event, not
the bug.

**Actions:** fix both lines; yank or supersede 1.3.0; make the release path refuse to tag
on red CI; restore the deleted `packages/pyapi/tests/test_daemon/` (only its `.pyc`
survives in git — had the test lived, it would have caught this).

### P1 — The ledger lies. This is the existential category.

Every item below is a **silent** wrong answer. For a lab notebook, silence is worse than a
crash, because you only discover it when you no longer remember what you ran.

| # | The lie | Where |
|---|---|---|
| 1 | **A crashed run is recorded as `SUCCESS`.** `close()` writes `SUCCESS` unconditionally and runs via `atexit`, which fires on uncaught exceptions too. The `CRASHED` path only triggers on SIGKILL — the *rarer* failure. `CRASHED` also has no entry in `_STATUS_STYLE`, so it renders indistinguishably from `N/A`. | [tracker.py:104](packages/pyapi/src/sillonpy/tracker.py), [display.py:59](packages/core/src/silloncore/display.py) |
| 2 | **Every server-side error is invisible to the client.** The server puts errors in the JSON-RPC **`result`** field; the client checks for a **top-level** `error` key that is never emitted. So `decode_response` never raises, `execute_command` returns `{"error": ...}`, and the tracker discards it. Failed logs are total no-ops the user never learns about. | [rpcHandler.py:84-97](packages/common/src/silloncommon/rpcHandler.py) vs [:63-67](packages/common/src/silloncommon/rpcHandler.py) |
| 3 | **One bad result silently discards every later result.** The `try` in `commit_result` wraps the whole loop; result #7 being un-typeable by h5py drops #7–50. The DB pointers were already written at log time, so the rows claim data that isn't there. | [glob.py:274-291](packages/core/src/silloncore/glob.py) |
| 4 | **Reading a lost result returns the pointer *string* instead of raising.** `load_result("coef")` hands back the literal `"coef"`. A test even asserts this as correct. Loss is undetectable by construction. | [engine.py:299-303](packages/core/src/silloncore/engine.py) |
| 5 | **One failed commit poisons the daemon for every later run.** A single long-lived `Session` with no `rollback()` — after one failure SQLAlchemy raises `PendingRollbackError` on every subsequent use, for the daemon's remaining 300 s. Cascading, silent, total. | [envhandler.py:111,178-184](packages/core/src/silloncore/envhandler.py) |
| 6 | **A failed dump is ACKed as success**, and `rm_sim` is skipped — pinning `sim_dict` non-empty, which permanently disables the idle timeout and leaks the h5py handle. | [server.py:216-224](packages/core/src/silloncore/server/server.py) |
| 7 | **Logging before `init()` gives `AttributeError: 'NoneType'`.** A good message was written — `RuntimeError("Tracker has not been initialized !")` — but `ContextVar(..., default=None)` means `LookupError` is never raised, so it is dead code. Verified. | [api.py:28-43](packages/pyapi/src/sillonpy/api.py) |
| 8 | **Custom storage roots are write-only.** `resolve_storage_root`'s lookup is commented out, so writers honour `config.toml` and every reader looks in `.sillon/`. Results read back as pointer strings; `prune` reports "freed 0.00 MB". | [project_paths.py:30-34](packages/core/src/silloncore/project_paths.py) |
| 9 | **Auto-generated run names skip the uniqueness check** that user-supplied names get. Two runs can share a name; `delete <name>` then wipes both. | [server.py:198-202](packages/core/src/silloncore/server/server.py), [simulation.py:240](packages/core/src/silloncore/simulation.py) |
| 10 | **The daemon never migrates the schema.** `create_default_engine_root` is the one engine factory not wrapped in `migrate_schema`; `create_all` adds tables, never columns. Old DB + new sillon → `OperationalError` → swallowed (#6) → poisoned session (#5) → every subsequent run lost. Whether you're safe depends on whether you happened to run a CLI command first. | [envhandler.py:108-112](packages/core/src/silloncore/envhandler.py), [database.py:84](packages/common/src/silloncommon/database.py) |

### P2 — Foundations that will not scale to your own stated workload

Measured, not guessed:

- **cProfile runs on every run, unconditionally, undocumented, no opt-out**, and dumps to a
  *relative* `profiling.txt` in the CWD. Measured **×2.15 on call-heavy Python numeric
  code**. Five `profiling.txt` files are committed to this repo. For multi-hour simulations
  this is the single largest cost in the system. Make it `sp.init(profile=False)` default.
  [tracker.py:66,87-96,108](packages/pyapi/src/sillonpy/tracker.py)
- **No WAL, no indexes.** Zero `journal_mode`/`PRAGMA` anywhere; only 3 `index=True`, all on
  `hsh`. `uuid`, `name`, `status`, `date` and all three `run_id` foreign keys are unindexed
  → `get_run_snapshot` is 4 full table scans, and `query_runs` calls it per surviving run:
  **O(N²)**. You already have WAL planned; the indexes are the other half and they are one line each.
- **`query_runs` loads every run's JSON into memory** with no `LIMIT` — measured ~14 KB of
  `meta_data` per run inflating 2.2× as Python objects. At 10k runs a single query is
  ~500 MB RSS. Most of that blob is a near-identical `sys_modules` list stored per run.
- **Every log call is a blocking round trip.** Measured **28 µs** for a scalar; **474 µs**
  for an 8 KB array (under the staging threshold, so `tolist()` → JSON → 2.56× ASCII
  inflation). No batching. `@track` costs 3–4 round trips per decorated call.
- **The commit stalls every other client.** Single-threaded `selectors` loop with a fully
  blocking `commit_run` (whole HDF5 write + 2 fsyncs) inline. With N concurrent sweep
  workers finishing together, stalls serialize. This is your stated workload.
- **`to_dataframe()` on `query()` results silently emits null `timestamp`/`status`** —
  dict literals evaluate top-to-bottom and read those attributes before anything triggers
  the lazy snapshot load. This breaks the exact line in your README.
  [run.py:644-650](packages/interface/sillonlab/src/sillonlab/run.py)

---

## Part 3 — Positioning: an honest correction, and why the opportunity is still real

**Your premise — "no alternative exists except AI" — is not accurate, and the real picture
is better news than the premise.**

Alternatives exist: MLflow, Weights & Biases, Neptune, Comet, Aim, ClearML, DVC/DVCLive,
guild.ai, Sacred, and — closest of all — [Sumatra](https://github.com/open-research/sumatra),
literally "an automated electronic lab notebook for computational projects."

But look at what they actually are:

- **The ML tools are shaped for the training loop.** Their primitive is a metric-vs-step
  curve: epochs, loss, checkpoints. A simulation is *parameters → arrays*, not a loss
  curve. Logging a 4-D field snapshot to MLflow is friction the whole way down.
- **The scientific-provenance tools are dormant.** Sumatra still self-describes as beta
  after a decade-plus, with 85 open issues and documentation on the long-dead
  `pythonhosted.org`. Sacred and recipy are similar.
- **The market's attention has left entirely.** Searching the 2026 "MLflow alternatives"
  discourse returns LLM-evaluation platforms — Langfuse, DeepEval, Braintrust, Opik. The
  simulation scientist has simply been abandoned.

So the gap is a **neglect gap, not a vacuum**. Strategically this is *better*: you don't
have to invent a category or educate a market — the job is well understood and the
incumbents do it badly. But it means **you win on trust and ergonomics, not on feature
count**, because a scientist evaluating you will compare against a tool that at least
doesn't lie about run status.

**The moat is the hashing + lineage axis.** Metric logging is commodity — anyone can add
it. Content-addressed provenance, `used=` figure lineage, and a real diff engine over runs
are not, and they're the things you already have taste for. My strong recommendation:
**treat lineage as the product, not as the feature that comes later**, and make sure the
storage decisions in Part 4 don't foreclose it.

---

## Part 4 — Architecture, given the console vision

Your answer reframed the daemon, and it reframes it *correctly*. If the daemon's future is
a live console of running processes, then it must persist and every run must transit it —
so "drop the daemon" was the wrong question and I'm setting it aside.

But one factual correction to the plan you described:

> **Parameter staging is already implemented** ([tracker.py:127-128](packages/pyapi/src/sillonpy/tracker.py)) —
> `log_param` already routes through `is_large_array` → `write_staging_array`, exactly like
> results. That part is done.
>
> **However, staging does not currently protect the daemon from OOM.** `save_from_staging`
> does `data = f["data"][()]` — it reads the entire array back into daemon RAM — then
> `save()` appends it to `self.results` where it stays until dump, and `get_hash` pickles a
> **second full copy** to hash it. Verified at
> [glob.py:232-237 and :29-32](packages/core/src/silloncore/glob.py). So staging today just
> *moves* the memory problem from the client to the daemon. Your reasoning was right; the
> implementation doesn't yet realize it.

### The shape to aim for: split the daemon's two jobs

The daemon is currently doing one job badly by conflating two:

| Job | Holds | Lives in |
|---|---|---|
| **Live run state** — status, name, progress, a few scalars. *This is the console.* | Kilobytes per run | RAM, legitimately |
| **Durable data** — results, params, arrays, figures | Unbounded | Disk, immediately |

Concretely:

1. **Never materialize staged arrays in the daemon.** Replace the read-into-RAM in
   `save_from_staging` with an HDF5-level copy (`dest.copy(src["data"], name)`), which
   streams without a Python object, then unlink. Big data goes client-disk → glob-disk and
   never enters daemon memory. Compute the hash **client-side**, where the array already
   lives, and ship it in the pointer dict — this also removes the `pickle.dumps` full copy.
2. **Write through for small values too.** Nothing should sit in `Glob.results` waiting for
   dump. This is what makes the periodic flush you described unnecessary for data.
3. **Insert the DB row at REGISTER, not at dump.** Status `RUNNING`, updated on transitions.
   This is the highest-leverage single change in the whole document because it gives you:
   - crash honesty — a dead run leaves a `RUNNING` row to reap, not nothing;
   - the console's data source, queryable by anything, not just daemon RAM;
   - `_handle_client_disconnect` becomes an UPDATE, not a lost insert;
   - and it kills the "buffer until dump, lose everything on crash" model outright.
4. **Get the commit off the event loop** — a worker thread with a queue, so one run's fsync
   doesn't freeze the sweep. Needed for your "concurrent workers, same machine" case.
5. **Give the protocol a read side.** The command registry is write-only today; a console
   needs `LIST_RUNS`/`GET_STATUS`. Note the three `Load*Cmd` classes already exist in
   `commands.py` with no server handler — dead code that hints at this.
6. **`IDLE_TIMEOUT = 300` conflicts with a console.** A monitor wants a daemon that persists.
   Make it configurable and long, or tie shutdown to explicit command.

One relief from your answers: **the NFS/SQLite multi-writer wall I would have flagged does
not apply to you** — one writer per project, own project per user, even on a cluster. WAL
plus indexes genuinely carries you. Cross-host stays a future concern, and the daemon's
socket abstraction (see the `windows_port` branch) is the right seam for it later.

---

## Part 5 — Roadmap

### Phase 0 — Stop the bleeding (days)
1. Fix `daemon.py:58,61`. Yank/supersede v1.3.0. Restore `test_daemon/`.
2. Make CI blocking on `main`; make the release path refuse on red.
3. Make cProfile opt-in; delete the five committed `profiling.txt`; untrack the ~73 `.pyc` files.

### Phase 1 — Make the record trustworthy (the real work)
4. **Real status**: `sys.excepthook`/`sys.last_exc` in `close()`; never write `SUCCESS`
   unconditionally; add `CRASHED` to `_STATUS_STYLE`.
5. **Loud failures**: emit a top-level JSON-RPC `error`; raise client-side; make `dump`
   report actual commit success. Fix `excute` → `execute` while there.
6. **Per-dataset error handling** in `commit_result`; make a missing dataset on read *raise*
   instead of returning the pointer string.
7. **`session.rollback()`** on commit failure; route the daemon's engine through
   `migrate_schema`; add a `schema_version` table and a version gate.
8. **Uniqueness for auto-generated names**; un-comment `resolve_storage_root`.
9. **Fix `get_context`** so the already-written error message fires.
10. **Tests for all of the above**, plus the ones that don't exist at all: crash recovery,
    daemon lifecycle, schema migration, concurrency, the error paths. Today's integration
    tests are the only thing touching the daemon, and `test_cli`/`test_sillonlab` build
    rows by hand — so the producer/consumer contract is entirely untested.

### Phase 2 — Foundations (Part 4)
11. WAL + `busy_timeout` + `synchronous=NORMAL`; `index=True` on `uuid`, `name`, `status`,
    `date` and the three `run_id` FKs.
12. Streaming staging claim + client-side hashing; write-through; row-at-REGISTER.
13. Commit off the event loop.
14. Kill the N+1 in `query_runs` (bulk snapshot path — `select_run_index` already exists);
    stop storing a near-identical `sys_modules` blob per run.

### Phase 3 — Ergonomics (what wins lab adoption)
15. **`--json` on every CLI command.** Handlers already return clean dicts; this is a
    serializer and a flag, and it turns a browsing tool into a scriptable one.
16. `RunCollection.sort_by()`; fix `to_dataframe`'s null `timestamp`/`status`.
17. `--project`/`-C` on the CLI; `sillon daemon status/stop`; `sillon doctor`.
18. Naming debt: `context` → `list` (aliased); decide between `add_metadata`/`log_metadata`
    rather than shipping both; rename `@track` to `@autolog` (it is categorically different
    from `track_run` and the name collision is the worst in the API); retire "glob" from
    user-facing docs — it means filename patterns to every Python user.
19. Fix the `examples/` directory: it logs a *result* via `log_param`, uses `sl` for
    `sillonpy` where the docs use it for `sillonlab`, and covers none of the distinctive
    features.

### Phase 4 — The moat
20. Lineage/diff engine, built on the hashing that already exists.
21. The live console — now cheap, because Phase 2 put run state in the DB.

---

## Verification

Each phase has a concrete gate:

```bash
make test
```

- **Phase 0 done** when a clean-checkout `python examples/basic-01/basic.py` logs a run, and
  CI is green on `main`.
- **Phase 1 done** when a test that raises inside a tracked script asserts the run reads back
  as `CRASHED`, and a test that makes the server fail a command asserts the client *raises*.
- **Phase 2 done** when a 1 GB `log_result` shows daemon RSS staying flat (measure with
  `psutil` in a test), and `query_runs` over a 10k-run fixture completes without loading
  every blob.
- **Phase 3 done** when `sillon search --json | jq` works.

The `windows_port` branch already carries the transport seam, the `os.kill` fix, WAL-adjacent
path fixes and a 3-OS CI matrix; it should land after Phase 0 so the CI discipline arrives
with it.
