PYTHON ?= python3
VIRTUAL_ENVIRONMENT := .venv
VIRTUAL_PYTHON := $(VIRTUAL_ENVIRONMENT)/bin/python
VIRTUAL_PYTEST := $(VIRTUAL_ENVIRONMENT)/bin/pytest
VIRTUAL_RUFF := $(VIRTUAL_ENVIRONMENT)/bin/ruff
SETUP_MARKER := $(VIRTUAL_ENVIRONMENT)/digitalizadora-setup-complete
SIMULATOR_SCANNER_ADDRESS := http://127.0.0.1:8080/eSCL
SIMULATED_HOME ?= $(HOME)/Digitalizadora-simulador

.PHONY: setup run simulator run-simulated test test-hardware lint check

setup:
	$(PYTHON) -m venv --clear $(VIRTUAL_ENVIRONMENT)
	$(VIRTUAL_PYTHON) -m pip install --upgrade pip
	$(VIRTUAL_PYTHON) -m pip install -e ".[development]"
	touch $(SETUP_MARKER)

run:
	$(VIRTUAL_PYTHON) -m digitalizadora

simulator:
	$(VIRTUAL_PYTHON) -m digitalizadora.simulator

run-simulated:
	HOME="$(SIMULATED_HOME)" DIGITALIZADORA_SCANNER_ADDRESS=$(SIMULATOR_SCANNER_ADDRESS) $(VIRTUAL_PYTHON) -m digitalizadora

test:
	$(VIRTUAL_PYTEST)

test-hardware:
	DIGITALIZADORA_HARDWARE_TESTS=1 $(VIRTUAL_PYTEST) -m hardware -v

lint:
	$(VIRTUAL_RUFF) check src tests

check: lint test
