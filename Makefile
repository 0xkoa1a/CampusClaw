PYTHON ?= .venv/bin/python

.PHONY: check worker
check:
	$(PYTHON) -m pytest -q

worker:
	$(PYTHON) -m app.worker
