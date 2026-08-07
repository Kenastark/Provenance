# Provenance - developer commands
# Every target here is expected to work on a fresh clone with no data present.

SHELL := /bin/bash
COMPOSE := docker compose -f infra/compose/docker-compose.yml
VENV := .venv
PY := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help
help: ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- environment
.PHONY: install
install: ## create .venv and install the package with dev extras (uv)
	uv venv --python 3.12
	uv pip install -e ".[dev]"
	@echo "Done. Activate with: source .venv/bin/activate"

.PHONY: install-pip
install-pip: ## fallback for machines without uv
	python3.12 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

.PHONY: hooks
hooks: ## install git pre-commit hooks
	$(VENV)/bin/pre-commit install

.PHONY: web-install
web-install: ## install frontend dependencies
	cd apps/web && pnpm install

# ---------------------------------------------------------------- quality
.PHONY: lint
lint: ## ruff check + format check + mypy strict
	$(VENV)/bin/ruff check src tests
	$(VENV)/bin/ruff format --check src tests
	$(VENV)/bin/mypy

.PHONY: format
format: ## autofix and format
	$(VENV)/bin/ruff check --fix src tests
	$(VENV)/bin/ruff format src tests

.PHONY: test
test: ## default test suite (excludes docker + slow)
	$(VENV)/bin/pytest

.PHONY: test-all
test-all: ## everything, including docker-dependent and slow tests
	$(VENV)/bin/pytest -m ""

.PHONY: web-test
web-test: ## frontend unit tests
	cd apps/web && pnpm test -- --run

.PHONY: check
check: lint test ## lint + test, the gate every phase must pass

# ---------------------------------------------------------------- services
.PHONY: up
up: ## start the local stack
	$(COMPOSE) up -d --wait

.PHONY: down
down: ## stop the local stack
	$(COMPOSE) down

.PHONY: logs
logs: ## tail service logs
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## service status
	$(COMPOSE) ps

# ---------------------------------------------------------------- product
.PHONY: fixtures
fixtures: ## generate the seeded synthetic corpus used by every test
	$(VENV)/bin/prov fixtures make --out tests/fixtures

.PHONY: audit
audit: ## run the audit over the real data drop
	$(VENV)/bin/prov audit run --data data/raw --out reports

.PHONY: demo
demo: ## bring up the stack, load fixtures, run the audit, open the dashboard
	$(MAKE) up
	$(VENV)/bin/prov db upgrade
	$(VENV)/bin/prov fixtures make --out tests/fixtures
	$(VENV)/bin/prov db load --source tests/fixtures
	$(VENV)/bin/prov audit run --data tests/fixtures --out reports
	@echo "Dashboard: http://localhost:5173  API docs: http://localhost:8000/docs"

.PHONY: clean
clean: ## remove caches and generated output
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf reports/* && touch reports/.gitkeep
