PYTHON ?= python3
RAIL := .venv/bin/rail

.PHONY: setup demo sync live test lint powerbi
setup:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -r requirements.lock
	.venv/bin/python -m pip install --no-deps -e .

demo:
	$(RAIL) demo

sync:
	$(RAIL) --mode live sync

live:
	$(RAIL) --mode live build
	$(RAIL) --mode live export

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src tests scripts
	.venv/bin/ruff format --check src tests scripts

powerbi:
	.venv/bin/python scripts/prepare_powerbi.py
	.venv/bin/python scripts/package_handoff.py
