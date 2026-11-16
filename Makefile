PYTHON ?= .venv/bin/python

.PHONY: check check-security worker
check:
	$(PYTHON) -m pytest -q

check-security:
	$(PYTHON) -m pytest -q tests/test_delivery.py tests/test_security_controls.py tests/test_observability.py tests/test_bearer.py tests/test_task_queue.py tests/test_async_grading.py
	$(PYTHON) scripts/check_security.py
	$(PYTHON) -m pip_audit -r requirements-dev.txt

worker:
	$(PYTHON) -m app.worker
