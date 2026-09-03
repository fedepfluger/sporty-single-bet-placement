# Convenience targets. Everything works with plain pytest too - see the README.
# Override the interpreter when `python3` is not the one you want, e.g.
#   make install PYTHON=/opt/homebrew/bin/python3.14
PYTHON ?= python3
VENV   ?= .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

.PHONY: help install hooks smoke regression api ui all report clean lint format check

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv and install every dependency
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	@$(PY) --version

hooks: ## Install the git pre-commit hooks
	$(VENV)/bin/pre-commit install

smoke: ## Fast gate: the critical paths only
	$(PY) -m pytest -m smoke

regression: ## Full validation matrix
	$(PY) -m pytest -m regression

api: ## Every API test
	$(PY) -m pytest -m api

ui: ## Every browser test
	$(PY) -m pytest -m ui

all: ## The whole suite
	$(PY) -m pytest

report: ## Open the Allure report for the last run
	allure serve reports/allure-results

lint: ## Static analysis, no files touched
	$(VENV)/bin/ruff check .
	$(VENV)/bin/black --check .
	$(VENV)/bin/isort --check-only .

format: ## Apply formatting
	$(VENV)/bin/black .
	$(VENV)/bin/isort .

check: ## Everything pre-commit would run
	$(VENV)/bin/pre-commit run --all-files

clean: ## Remove reports and caches
	rm -rf reports/allure-results reports/allure-report .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
