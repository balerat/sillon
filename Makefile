.PHONY: install test docs build

# Editable dev install of the single `sillon` distribution (with dev extras).
install:
	pip install -e ".[dev]"

test:
	pytest ./packages/common/tests/ ./packages/pyapi/tests/ ./packages/core/tests/ ./packages/interface/sillonlab/tests/ ./packages/interface/cli/tests/

# Build the sdist + wheel into dist/
build:
	python -m build

docs:
	mkdocs serve
