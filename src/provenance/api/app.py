"""The FastAPI application factory.

``create_app`` wires the engine, sessionmaker, middleware, error handlers, and
every router. It takes an optional engine so a test can pass a SQLite engine and
run the real routers unchanged; production calls it with no argument and gets the
configured Postgres engine. The app owns the sessionmaker on ``app.state`` and
disposes the engine on shutdown.
"""

from __future__ import annotations

import os

# macOS/Homebrew/arm64 only: torch and scikit-learn each load their own copy of
# LLVM's libomp.dylib, and the two colliding inside a real OS thread (exactly what
# run_in_threadpool spawns for /v1/graph/attention's HST-GAT forward pass) SIGSEGVs
# the whole process (docs/updates/u14-train-hstgat-real.md, u17-evidence-review-
# fixes.md). `KMP_DUPLICATE_LIB_OK=TRUE` does not help - that variable is for
# Intel's iomp5, not LLVM's libomp; forcing single-threaded OpenMP does. Set here,
# before any router import below can pull torch in transitively, so every way of
# starting the API is protected - not just `make api`/`api-bg`, which used to be
# the only guarded path (their `OMP_NUM_THREADS=1` prefix is now a harmless second
# layer). Deliberately scoped to this module rather than provenance/__init__.py:
# CLI training commands and the pytest suite still want their threads, and only
# importing the API app needs this.
os.environ.setdefault("OMP_NUM_THREADS", "1")

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from provenance import __version__
from provenance.api.deps import get_data_raw
from provenance.api.errors import install_error_handlers
from provenance.api.logging import RequestContextMiddleware
from provenance.api.metrics import MetricsMiddleware, metrics_endpoint
from provenance.api.routers import (
    admin,
    alerts,
    audit,
    decision,
    defects,
    deweather,
    events,
    explain,
    export,
    graph,
    maintenance,
    meta,
    quality,
    readings,
    reference,
    stations,
    trust,
)
from provenance.config.settings import get_settings
from provenance.io.db.engine import make_engine, make_sessionmaker

_ROUTERS = (
    meta.router,
    stations.router,
    reference.router,
    readings.router,
    defects.router,
    trust.router,
    quality.router,
    events.router,
    audit.router,
    export.router,
    explain.router,
    deweather.router,
    graph.router,
    maintenance.router,
    alerts.router,
    decision.router,
    admin.router,
)

_DESCRIPTION = (
    "The operator-facing trust layer for the Green Sentinel environmental sensor "
    "network. Every trust score carries its component breakdown and at least one "
    "reason code; no endpoint returns a bare number."
)


def create_app(engine: AsyncEngine | None = None, data_raw: Path | None = None) -> FastAPI:
    owns_engine = engine is None
    engine = engine or make_engine()
    sessionmaker = make_sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _warm_model_caches()
        yield
        if owns_engine:
            await engine.dispose()

    app = FastAPI(
        title="Provenance API",
        version=__version__,
        description=_DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    # A test-only override: passing data_raw swaps get_data_raw's return value
    # via FastAPI's own dependency-override mechanism, so the reference routers
    # never depend on anything reachable from the request itself (see deps.py).
    if data_raw is not None:
        app.dependency_overrides[get_data_raw] = lambda: data_raw

    # The dashboard runs on its own origin, so without CORS every browser request
    # fails preflight and the screens render empty against a perfectly healthy API.
    # An explicit allow-list, never "*": the API authenticates with a header key,
    # and a wildcard origin would let any page spend an operator's credentials.
    # GET for the read product; POST for the phase-7 operator/admin write actions
    # (maintenance transitions, sign-off, dispatch, retrain). Still an explicit
    # allow-list, never "*": the API authenticates with a header key.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-API-Key", "Accept", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    # Infra-plane monitoring: time every request, expose the Prometheus scrape at
    # /metrics (unauthenticated, like the other meta probes). Model drift is a separate
    # plane behind /v1/admin/model-drift.
    app.add_middleware(MetricsMiddleware)
    app.add_route("/metrics", metrics_endpoint, methods=["GET"])
    install_error_handlers(app)
    for router in _ROUTERS:
        app.include_router(router)
    return app


def _warm_model_caches() -> None:
    """Load the trained artefacts once at startup so no request pays the disk read.

    Best-effort by construction. A missing artefact is a normal state (standing rule 6):
    the cached loaders return ``None``, nothing is cached, and every caller degrades to
    the statistics layer exactly as it does today — just cold instead of warm. A *corrupt*
    store (an artefact whose card is missing or mismatched) raises inside the loader; it is
    caught and logged here too, because refusing to start the API is a worse failure than
    serving the statistics layer and saying so. The first request then retries the load and
    surfaces the same error through its normal path.

    Imported inside the function, like the routers do, so importing this module still does
    not pull torch in (``models/hstgat/store.py`` docstring).
    """
    from provenance.models import registry
    from provenance.models.hstgat import store as hstgat_store

    logger = logging.getLogger(__name__)
    try:
        if registry.load_bundle_cached() is None:
            logger.info(
                "No deweather/fault artefact at startup; serving degraded until one exists."
            )
    except Exception:  # a model artefact must never stop the API starting
        logger.warning("Could not warm the deweather/fault cache at startup.", exc_info=True)
    try:
        if hstgat_store.load_latest_cached() is None:
            logger.info("No HST-GAT artefact at startup; the analytic prior serves the graph.")
    except Exception:  # a model artefact must never stop the API starting
        logger.warning("Could not warm the HST-GAT cache at startup.", exc_info=True)
