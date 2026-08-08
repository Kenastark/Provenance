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
web-test: ## frontend unit tests with the coverage gate
	cd apps/web && pnpm test:coverage

.PHONY: web-lint
web-lint: ## frontend lint + typecheck
	cd apps/web && pnpm lint && pnpm typecheck

.PHONY: web-e2e
web-e2e: ## Playwright end-to-end suite (needs the stack + demo data)
	cd apps/web && pnpm e2e

.PHONY: web-contract
web-contract: ## regenerate the frontend's copy of the API contract
	$(VENV)/bin/python scripts/gen_frontend_contract.py
	cd apps/web && pnpm gen:types

.PHONY: web-contract-check
web-contract-check: ## fail if the generated client has drifted from the backend
	$(VENV)/bin/python scripts/gen_frontend_contract.py --check
	cd apps/web && pnpm gen:types && git diff --exit-code -- src/api/schema.d.ts

.PHONY: check
check: lint test web-contract-check ## lint + test + contract drift, the gate every phase must pass

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

# The demo corpus is deliberately NOT tests/fixtures. The test corpus is four
# stations and is pinned by the golden ledger; the demo corpus is the same seeded
# generator asked for a network the size of the real one (16 land + 2 water = 18)
# so the map has a network on it. Both are synthetic; neither needs data/raw.
DEMO_DIR := .demo-corpus
DEMO_STATIONS := 18

.PHONY: demo-corpus
demo-corpus: ## generate the 18-station demo corpus (synthetic, with coordinates)
	$(VENV)/bin/prov fixtures make --out $(DEMO_DIR) --stations $(DEMO_STATIONS)

.PHONY: demo-data
demo-data: demo-corpus ## schema, demo corpus, audit - everything but the servers
	$(VENV)/bin/prov db upgrade
	$(VENV)/bin/prov db load --source $(DEMO_DIR)
	$(VENV)/bin/prov audit run --data $(DEMO_DIR) --out reports

.PHONY: demo
demo: ## one command: stack up, demo corpus loaded, audit run, dashboard open
	$(MAKE) up
	$(MAKE) demo-data
	cd apps/web && pnpm install --no-frozen-lockfile && pnpm build
	@echo ""
	@echo "  Dashboard : http://localhost:5173   (run 'make web' if it is not already up)"
	@echo "  API docs  : http://localhost:8000/docs"
	@echo ""
	$(MAKE) web

.PHONY: web
web: ## run the dashboard dev server
	cd apps/web && pnpm dev

.PHONY: clean
clean: ## remove caches and generated output
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf reports/* && touch reports/.gitkeep
