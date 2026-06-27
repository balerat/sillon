# Development setup

### Prerequisites

- Git
- Python ≥ 3.11

### Setup

```bash
git clone https://github.com/balerat/sillon.git
cd sillon

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"            # editable install + test/build tooling  (or: make install)
```

`sillon` builds as a **single distribution** from one root `pyproject.toml` that ships all five
import packages (`silloncommon`, `silloncore`, `sillonpy`, `silloncli`, `sillonlab`) — there are
no per-package installs. The editable install gives you both console commands immediately:

```bash
sillon --help
```

### Running tests

```bash
make test
# equivalently:
pytest packages/common/tests packages/core/tests packages/pyapi/tests \
       packages/interface/sillonlab/tests packages/interface/cli/tests
```

The suite runs in a fresh checkout with no extra setup: the logging server self-spawns via the
current interpreter, so no console script needs to be on `PATH`.

### Building the docs

```bash
pip install -e ".[docs]"
mkdocs serve            # live preview at http://127.0.0.1:8000
mkdocs build --strict   # fails on broken links / missing nav entries
```
