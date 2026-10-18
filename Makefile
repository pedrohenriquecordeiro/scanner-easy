.PHONY: setup test lint

PYTHON ?= python3
VIRTUAL_ENVIRONMENT := .venv

setup:
	$(PYTHON) -m venv $(VIRTUAL_ENVIRONMENT)
	$(VIRTUAL_ENVIRONMENT)/bin/pip install -e ".[development]"

test:
	$(VIRTUAL_ENVIRONMENT)/bin/pytest

lint:
	$(VIRTUAL_ENVIRONMENT)/bin/ruff check src tests
