# Welcome to sillon Docs

### Quick Navigation
* [Installation Guide](installation.md)
* [How to Contribute](contribute.md)
* [Architecture Overview](architecture.md)
* [sillonPy API](sillonpy.md)
* [sillonCore](silloncore.md)
* [sillonCommon](silloncommon.md)

---

### What is the project?
sillon is a devtool chain aimed at logging and tracking simulation runs. You can think of it as the "Git for simulations." It is intuitive and easy to use.

sillon can log simulation parameters, metadata, tags, results, figures (with data provenance), and post-hoc analyses. The toolchain currently ships:

- a **Python logging API** (`sillonpy`) to track runs from a simulation script,
- a **background server** that writes runs to SQLite + HDF5,
- a **CLI** (`sillon`) to explore, search, fetch, prune, and report on runs,
- an **analysis library** (`sillonlab`) to load and analyze runs in scripts or notebooks.

#### Roadmap (not yet implemented)
The following are planned but **not** part of the current release: a GUI, a collaborative web
platform, Slurm integration, run reproduction/relaunch, a live-monitoring TUI, resource
estimation, and native APIs for other languages (C++, etc.).

### What is this website?
This website is the internal wiki for sillon's development. It contains all the project documentation, architectural guides, installation instructions, and contribution guidelines. It is built with MkDocs directly from our monorepo and deployed automatically via GitHub Actions, which pulls the docstrings straight from our code to populate the API references.

### How to navigate the wiki
There is a dedicated page for each component of the toolchain. If you are new here, we highly recommend reading the [Architecture Design](architecture.md) page, the [Installation Guide](installation.md), and our guide on [How to Contribute](contribute.md) to get up to speed.

Every new developer should review these core pages to understand the project's foundation.
