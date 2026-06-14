.PHONY:
	install test docs

install:
	pip install -e ./packages/common/ -e ./packages/interface/cli -e ./packages/interface/sillonlab -e ./packages/pyapi/ -e ./packages/core/

test:
	pytest ./packages/common/tests/ ./packages/pyapi/tests/ ./packages/core/tests/ ./packages/interface/sillonlab/tests/ ./packages/interface/cli/tests/

docks:
	mkdocs serve
