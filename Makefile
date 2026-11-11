PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install run test lint install-hooks check-sensitive

install:
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) -m uvicorn api.main:app --host 0.0.0.0 --port 8000

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

install-hooks:
	git config core.hooksPath .githooks

check-sensitive:
	$(PYTHON) scripts/check_sensitive.py
