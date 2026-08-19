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

# Visual baselines are pinned to two environments, and only two.
#
# Font rasterisation and antialiasing differ enough between platforms that a
# baseline is only meaningful against the environment that produced it - and that
# is true between macOS and Linux *and* between a bare Ubuntu runner and the
# official Playwright image, whose font sets differ. Rather than chase that, the
# Linux baselines are both generated and verified inside the same pinned image, so
# CI compares like with like. macOS baselines exist so the gate is real on a
# developer's laptop too.
#
# The container copy drops public/basemap before building, so the visual gate always
# tests the token-ground default - the state a fresh clone and CI have. The fetched
# street basemap is a local enhancement and is deliberately not under pixel
# regression (its tiles come from an upstream planet that changes daily).
PLAYWRIGHT_IMAGE := mcr.microsoft.com/playwright:v1.62.1-noble
VISUAL_API_URL ?= http://host.docker.internal:8000

define run_visual_in_container
	docker run --rm \
	  -v "$(PWD)/apps/web:/host:ro" \
	  -v "$(PWD)/apps/web/e2e/visual.spec.ts-snapshots:/out" \
	  -e VITE_API_BASE_URL=$(VISUAL_API_URL) \
	  --add-host=host.docker.internal:host-gateway \
	  $(PLAYWRIGHT_IMAGE) \
	  bash -lc 'set -e; corepack enable pnpm >/dev/null 2>&1 || true; \
	    curl -sf "$$VITE_API_BASE_URL/healthz" >/dev/null || { \
	      echo "The API is not reachable at $$VITE_API_BASE_URL from inside the"; \
	      echo "container. Start it with: make api-bg  (and make demo-data first)."; \
	      echo "On Linux the API must bind 0.0.0.0, not 127.0.0.1, or the Docker"; \
	      echo "bridge cannot reach it. Without data every screenshot is blank."; \
	      exit 1; }; \
	    mkdir -p /build && cp -r /host/. /build/; \
	    rm -rf /build/node_modules /build/dist /build/test-results /build/playwright-report; \
	    rm -rf /build/public/basemap; \
	    cd /build && pnpm install --no-frozen-lockfile --silent; \
	    npx playwright test --project=chromium e2e/visual.spec.ts $(1); \
	    cp /build/e2e/visual.spec.ts-snapshots/*-linux.png /out/ 2>/dev/null || true'
endef

.PHONY: web-visual-linux
web-visual-linux: ## regenerate the Linux visual baselines in the pinned image (needs the API up)
	$(call run_visual_in_container,--update-snapshots)

.PHONY: web-visual-check
web-visual-check: ## verify the Linux visual baselines in the pinned image (needs the API up)
	$(call run_visual_in_container,)

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
demo-data: demo-corpus ## schema, demo corpus, audit, adjudication - everything but the servers
	$(VENV)/bin/prov db upgrade
	$(VENV)/bin/prov db load --source $(DEMO_DIR)
	$(VENV)/bin/prov audit run --data $(DEMO_DIR) --out reports
	$(VENV)/bin/prov graph adjudicate-db --source $(DEMO_DIR)
	$(VENV)/bin/prov graph adjudicate --data $(DEMO_DIR) --out reports/adjudications

# Model training is deliberately NOT part of demo-data: the visual-regression
# baselines are captured with demo-data (no models), so the trust score reads
# `degraded` there and the station panel shows its degraded badge - the pinned state.
# `make demo` trains the phase-5 models on top, which lights up the evidence panel's
# SHAP attributions and the before/after deweathering chart for the live run.
.PHONY: demo-models
demo-models: ## train the phase-5 models on the demo corpus and store its residuals
	$(VENV)/bin/prov models train --source $(DEMO_DIR)
	$(VENV)/bin/prov models residuals --source $(DEMO_DIR)

API_PID := .demo-api.pid
# Loopback locally. CI overrides it to 0.0.0.0 so the browser running inside the
# pinned Playwright container can reach back through the Docker bridge.
API_HOST ?= 127.0.0.1

.PHONY: api
api: ## run the API in the foreground
	$(VENV)/bin/python -m uvicorn provenance.api.app:create_app --factory \
	  --host $(API_HOST) --port 8000 --reload

.PHONY: api-bg
api-bg: ## start the API in the background (writes $(API_PID))
	@if curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1; then \
	  echo "API already listening on :8000"; \
	else \
	  $(VENV)/bin/python -m uvicorn provenance.api.app:create_app --factory \
	    --host $(API_HOST) --port 8000 > .demo-api.log 2>&1 & echo $$! > $(API_PID); \
	  for i in $$(seq 1 40); do \
	    curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1 && break; sleep 1; \
	  done; \
	  curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1 \
	    && echo "API listening on :8000 (pid $$(cat $(API_PID)), log .demo-api.log)" \
	    || { echo "API failed to start; see .demo-api.log"; exit 1; }; \
	fi

.PHONY: basemap
basemap: ## fetch the Debrecen street basemap (once; needs network; offline after)
	bash scripts/fetch-basemap.sh

.PHONY: demo
demo: ## one command: stack up, demo corpus loaded and audited, API up, dashboard open
	$(MAKE) up
	$(MAKE) demo-data
	$(MAKE) demo-models
	$(MAKE) api-bg
	cd apps/web && pnpm install --no-frozen-lockfile
	@# The streets are a nice-to-have. If the fetch cannot reach the network, the
	@# demo still runs against the token-coloured ground, so this must never abort it.
	$(MAKE) basemap || echo "  basemap: skipped — the map will use the token ground"
	@echo ""
	@echo "  Dashboard : http://localhost:5173"
	@echo "  API docs  : http://localhost:8000/docs"
	@echo "  Stop with : make demo-stop"
	@echo ""
	$(MAKE) web

.PHONY: demo-scenarios
demo-scenarios: ## write the deterministic replay sequences for every scenario (offline)
	$(VENV)/bin/prov demo rehearse --data $(DEMO_DIR) --out reports/demo

.PHONY: demo-record
demo-record: ## capture the demo to a fallback recording (replay sequences + best-effort video)
	bash scripts/record-demo.sh

.PHONY: demo-stop
demo-stop: ## stop the background API and the local stack
	@if [ -f $(API_PID) ]; then kill $$(cat $(API_PID)) 2>/dev/null || true; rm -f $(API_PID); fi
	$(MAKE) down

.PHONY: web
web: ## run the dashboard dev server
	cd apps/web && pnpm dev

.PHONY: clean
clean: ## remove caches and generated output
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf reports/* && touch reports/.gitkeep
