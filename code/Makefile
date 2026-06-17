.PHONY: test benchmark clean venv

VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

venv: $(VENV)/bin/activate

test: venv
	$(PYTEST) tests/ -v

benchmark: venv
	$(PYTHON) tests/benchmark.py

clean:
	rm -rf $(VENV) __pycache__ cubrim_proto/__pycache__ tests/__pycache__ \
	       *.pyc cubrim_proto/*.pyc tests/*.pyc \
	       docs/ephemeral/research/corpus/
