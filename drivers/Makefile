.PHONY: typehint
typehint:
	mypy --ignore-missing-imports --check-untyped-defs intake_geokube 
	pylint intake_geokube

.PHONY: test
test:
	pytest tests/

.PHONY: format
format:
	isort intake_geokube
	black intake_geokube
	black tests/
	isort tests/

.PHONY: docs
docs:
	pydocstyle -e --convention=numpy intake_geokube

prepublish: format typehint docs test
