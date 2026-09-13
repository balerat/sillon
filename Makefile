.PHONY: install test test-tcp docs build

# Editable dev install of the single `sillon` distribution (with dev extras).
install:
	pip install -e ".[dev]"

test:
	pytest ./packages/common/tests/ ./packages/pyapi/tests/ ./packages/core/tests/ ./packages/interface/sillonlab/tests/ ./packages/interface/cli/tests/

# Same suite over the loopback-TCP transport, i.e. the one Windows uses.
# Lets you exercise the Windows IPC path without a Windows machine.
test-tcp:
	SILLON_TRANSPORT=tcp $(MAKE) test

# Build the sdist + wheel into dist/
build:
	python -m build

docs:
	mkdocs serve
