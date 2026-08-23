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
# The container copy drops public/basemap and public/fonts before building, so the
# visual gate always tests the token-ground default - the state a fresh clone and CI
# have. The fetched street basemap and its glyph fonts (ADR 0011) are a local
# enhancement and are deliberately not under pixel regression (the tiles come from an
# upstream planet that changes daily, and nothing exercises the labelled state here).
PLAYWRIGHT_IMAGE := mcr.microsoft.com/playwright:v1.62.1-noble
VISUAL_API_URL ?= http://host.docker.internal:8000

# CI runs on amd64. Pinning the container to it (Rosetta/QEMU-emulated on an
# Apple Silicon host) keeps the baseline captured here identical to CI's,
# rather than each Mac's native arm64 build of the image - which font-hints
# text just differently enough to fail the gate on every push from one.

define run_visual_in_container
	docker run --rm \
	  --platform linux/amd64 \
	  -v "$(PWD)/apps/web:/host:ro" \
	  -v "$(PWD)/apps/web/e2e/visual.spec.ts-snapshots:/out" \
	  -v "$(PWD)/apps/web/test-results:/results" \
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
	    rm -rf /build/public/basemap /build/public/fonts; \
	    cd /build && pnpm install --no-frozen-lockfile --silent; \
	    set +e; npx playwright test --project=chromium e2e/visual.spec.ts $(1); status=$$?; set -e; \
	    cp /build/e2e/visual.spec.ts-snapshots/*-linux.png /out/ 2>/dev/null || true; \
	    cp -r /build/test-results/. /results/ 2>/dev/null || true; \
	    exit $$status'
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
# 60 days, not the real network's confirmed 30 (schema_assumptions.yaml
# window_days): the deweather regressor's forward-chaining CV needs enough rows
# in its early folds to converge past the golden-4's fixed-hour R07 outlier
# (STA-03's 3000 µg/m3 PM10 spike) without overfitting around it - below ~45
# days the reported PM10 R² stays negative or flips sign fold to fold; at 60 it
# is positive and stable across all folds. See docs/updates/u7-demo-corpus-wind.md.
DEMO_DAYS := 60

.PHONY: demo-corpus
demo-corpus: ## generate the 18-station demo corpus (synthetic, with coordinates, wind + a plume/fault pair)
	$(VENV)/bin/prov fixtures make --out $(DEMO_DIR) --stations $(DEMO_STATIONS) --days $(DEMO_DAYS) --with-weather --with-plume

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
# macOS/Homebrew/arm64 only: torch and scikit-learn each load their own copy of
# LLVM's libomp.dylib, and the two colliding inside a real OS thread (exactly what
# `run_in_threadpool` spawns for /v1/graph/attention's HST-GAT forward pass) SIGSEGVs
# the whole process - reproducible, not a logic bug (see
# docs/updates/u14-train-hstgat-real.md's "Flag for review"; the Evidence tab's
# attention card now calling that endpoint on every defect view, unconditionally,
# makes it near-certain to hit rather than only possible on a manual map-layer
# toggle). `KMP_DUPLICATE_LIB_OK=TRUE` does not help (that variable is for Intel's
# iomp5, not LLVM's libomp); forcing single-threaded OpenMP does, confirmed by
# repeated reproduction just now. `provenance/api/app.py` now sets the same env var
# itself before its router imports can pull torch in, so this is a second, harmless
# layer rather than the only guard - it also covers the plain `uvicorn` command in
# docs/api/README.md and any other way of starting the API these two targets don't.
# Not applied to the whole Makefile - `infra/docker/api.Dockerfile`'s Debian/glibc
# image uses a different OpenMP runtime (libgomp) and isn't known to share this
# failure mode, so it is left alone rather than paying this same throttling cost
# somewhere it may not be needed.
API_ENV := OMP_NUM_THREADS=1

.PHONY: api
api: ## run the API in the foreground
	$(API_ENV) $(VENV)/bin/python -m uvicorn provenance.api.app:create_app --factory \
	  --host $(API_HOST) --port 8000 --reload

.PHONY: api-bg
api-bg: ## start the API in the background (writes $(API_PID))
	@if curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1; then \
	  echo "API already listening on :8000"; \
	else \
	  $(API_ENV) $(VENV)/bin/python -m uvicorn provenance.api.app:create_app --factory \
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

.PHONY: fonts
fonts: ## fetch the basemap's street/place-label glyph fonts (once; needs network; offline after; ADR 0011)
	bash scripts/fetch-fonts.sh

.PHONY: demo
demo: ## one command: stack up, demo corpus loaded and audited, API up, dashboard open
	$(MAKE) up
	$(MAKE) demo-data
	$(MAKE) demo-models
	$(MAKE) api-bg
	cd apps/web && pnpm install --no-frozen-lockfile
	@# The streets and their labels are a nice-to-have. If either fetch cannot reach
	@# the network, the demo still runs (token ground, or streets with no labels),
	@# so neither may ever abort it.
	$(MAKE) basemap || echo "  basemap: skipped — the map will use the token ground"
	$(MAKE) fonts || echo "  fonts: skipped — the map will show streets with no labels"
	@echo ""
	@echo "  Dashboard : http://localhost:5173"
	@echo "  API docs  : http://localhost:8000/docs"
	@echo "  Stop with : make demo-stop"
	@echo ""
	$(MAKE) web

.PHONY: check-real-drop
check-real-drop: ## fail loudly if data/raw has no real drop to load (no silent fixture fallback)
	@if [ -z "$$(find data/raw -type f ! -name '.gitkeep' 2>/dev/null)" ]; then \
	  echo ""; \
	  echo "  data/raw is EMPTY (only .gitkeep placeholders) - there is no real Green"; \
	  echo "  Sentinel drop to load."; \
	  echo ""; \
	  echo "  'make demo-real' refuses to fall back to the synthetic fixtures; that"; \
	  echo "  fallback is what 'make demo' is for. Put the real export under data/raw"; \
	  echo "  (e.g. data/raw/green_sentinel/<drop>/DEB-KER*/*.xlsx) and try again."; \
	  echo ""; \
	  exit 1; \
	fi

.PHONY: demo-real
demo-real: check-real-drop ## one command against the REAL Green Sentinel drop in data/raw: stack up, DB loaded, audited, adjudicated, models trained (incl. HST-GAT, cached across re-runs), API up, dashboard open
	$(MAKE) up
	@# station_id and parameter name are global primary keys shared by every batch
	@# ever loaded (synthetic demo stations use the same STA-xx ids and the same
	@# pollutant vocabulary as the real DEB-KERnn export in places). A reset, not
	@# just an upgrade, keeps this target's map and audit showing the real drop
	@# only, never a mix of leftover synthetic markers and real ones. Local dev
	@# data only; regenerate the synthetic side any time with `make demo-data`.
	$(VENV)/bin/prov db reset --yes
	@# Pre-flight for the two graph models that make the REAL demo real, run BEFORE
	@# `db load` below: trust scores are precomputed and stored at load time (see
	@# `_insert_trust_scores` in io/db/loader.py), so the imputation model has to
	@# exist before that pass runs, or the ImputationUncertainty term would only
	@# pick it up on a second load. Neither command touches the DB - both read
	@# data/raw directly - so training first costs nothing else.
	@# The check IS `--skip-if-cached`'s own file/card-existence + content-checksum
	@# comparison (see train-hstgat/train-imputation in cli/main.py) - a cheap
	@# glob/exists test, no model load - so a separate metadata-only check would
	@# only duplicate it. `demo-real` can therefore be both correct by default
	@# (nothing silently stale or missing) and fast on every run but the first on a
	@# given machine: this is a deliberate reversal of U14's "kept as its own manual
	@# step" reasoning, which held only when the choice was "always train" vs.
	@# "never train automatically" - with a cheap existence check that trade-off no
	@# longer exists. A calibration that doesn't pass prints loudly (yellow) but
	@# never aborts this target or blocks the dashboard from starting (see
	@# `calibrate_and_coverage`'s honest refusal).
	@echo ""
	@echo "  Pre-flight: HST-GAT and imputation models (cached, or trained now) -----"
	@echo ""
	$(VENV)/bin/prov models train-hstgat --source data/raw --target PM10 --skip-if-cached
	$(VENV)/bin/prov models train-imputation --source data/raw --skip-if-cached
	$(VENV)/bin/prov db load --source data/raw
	$(VENV)/bin/prov audit run --data data/raw --out reports
	$(VENV)/bin/prov graph adjudicate-db --source data/raw
	$(VENV)/bin/prov graph adjudicate --data data/raw --out reports/adjudications
	$(VENV)/bin/prov models train --source data/raw
	$(VENV)/bin/prov models residuals --source data/raw
	$(MAKE) api-bg
	cd apps/web && pnpm install --no-frozen-lockfile
	@# The streets and their labels are a nice-to-have. If either fetch cannot reach
	@# the network, the demo still runs (token ground, or streets with no labels),
	@# so neither may ever abort it.
	$(MAKE) basemap || echo "  basemap: skipped — the map will use the token ground"
	$(MAKE) fonts || echo "  fonts: skipped — the map will show streets with no labels"
	@echo ""
	@echo "  REAL Green Sentinel drop loaded from data/raw"
	@echo "  Dashboard : http://localhost:5173"
	@echo "  API docs  : http://localhost:8000/docs"
	@echo "  Stop with : make demo-stop"
	@echo "  The Attention overlay map layer is already live for this drop above."
	@echo "  Force a fresh HST-GAT: make demo-real-hstgat"
	@echo "  Force fresh imputation models: make demo-real-imputation"
	@echo ""
	$(MAKE) web

# A separate, always-retrains target for forcing a fresh HST-GAT (a config or code
# change that `demo-real`'s checksum-based cache wouldn't detect, since that cache
# key is the data drop's content, not the model config). `demo-real` above already
# auto-trains this one if missing and skips it if cached (its own pre-flight, see
# the comment above the `models train-hstgat`/`train-imputation` lines there) - this
# target is ONLY for a deliberate retrain, never the only path to a working demo.
.PHONY: demo-real-hstgat
demo-real-hstgat: check-real-drop ## force-retrain the HST-GAT + conformal calibration on the REAL drop (demo-real already auto-trains this if missing/skips it if cached; use this only to force a fresh retrain)
	$(VENV)/bin/prov models train-hstgat --source data/raw --target PM10
	@echo ""
	@echo "  HST-GAT trained on the real Green Sentinel drop (data/raw)."
	@echo "  Parameter count and conformal coverage are reported above."
	@echo "  The dashboard's 'Attention overlay' map layer will enable itself next"
	@echo "  time it is loaded - no restart needed, GET /v1/graph/attention checks"
	@echo "  store.latest_stem() live."
	@echo ""

# Same discipline as demo-real-hstgat, above, for the per-parameter imputation
# models: demo-real already auto-trains-or-skips these; this target is only for a
# deliberate retrain (model-code change, or refreshing calibration).
.PHONY: demo-real-imputation
demo-real-imputation: check-real-drop ## force-retrain the imputation models + calibration on the REAL drop (demo-real already auto-trains this if missing/skips it if cached; use this only to force a fresh retrain)
	$(VENV)/bin/prov models train-imputation --source data/raw
	@echo ""
	@echo "  Imputation models trained on the real Green Sentinel drop (data/raw)."
	@echo "  Parameter count and conformal coverage per parameter are reported above."
	@echo "  The trust score's ImputationUncertainty term picks these up on the next"
	@echo "  'prov db load' (it is precomputed at load time, not served live)."
	@echo ""

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
