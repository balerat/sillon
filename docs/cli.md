# sillonCLI Reference

**The Command Line Interface for the sillon Ecosystem.**

sillonCLI is the bedrock of the sillon experience. While **Common** handles the backend logic and heavy lifting, sillonCLI provides the primary interface for the user to interact with the system. It is designed to be the daily driver for engineers and researchers, unleashing the full power of the platform—far beyond what the basic logging API offers.

Whether managing simulations, analyzing results, or cleaning up disk space, sillonCLI defines how users interact with their data.

## Architecture

* The `main.py` file contain the main function `cli` that is the cli function.
* Each command and their subparser are defined in python files in the `command` folder.

## Key Features

* **Querying:** Search for runs by parameter value, or by the presence of a result or artifact.
* **Context Awareness:** View a run's metadata, parameters, results, tags, and notes.
* **Comparison Engine:** Diff two runs to spot changes in parameters and source code.
* **Disk Hygiene:** `prune` to delete a run's stored data while optionally keeping its metadata.
* **Artifact Retrieval:** `grab` a specific result/artifact/figure from storage as a file.
* **Reporting:** `report` a self-contained context bundle (manifest + readable summary + source).
* **Knowledge Management:** Tag runs and attach notes.

## Command Reference

All commands run from inside a sillon project directory (one containing a `.sillon` folder).

```bash
# Search runs by parameter value, result, or artifact presence
sillon search -p optimizer=adam lr=0.01 -r coef -a mesh --limit 20
```
```bash
# Add notes / tags to runs
sillon add [run_id] --note "My comment" --tag production
```
```bash
# Context overview of the project, or a card per run
sillon context [run_id ...]
```
```bash
# Show detailed parameters / results / metadata
sillon show [run_ids] -p [parameters] -r [results] -m [metadata]
```
```bash
# Compare two runs (parameter and source diff)
sillon compare [run_id_A] [run_id_B]
```
```bash
# Fetch a result/artifact/figure as a file on disk
sillon grab [run_id] -r [result_name] --dest [dir]
```
```bash
# Free disk space: drop a run's data (keeps metadata by default)
sillon prune --run-id [id] --older-than 30d [--delete-metadata]
```
```bash
# Export a self-contained context bundle (zip) for a run
sillon report [run_id] --dest [out.zip] [--with-data]
```

> Planned for a future release (not yet available): `watch` (live TUI), `estimate` (resource
> prediction), `source` (standalone source viewer), and `run` (relaunch/reproduce).
