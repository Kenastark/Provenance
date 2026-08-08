"""The FastAPI application factory.

``create_app`` wires the engine, sessionmaker, middleware, error handlers, and
every router. It takes an optional engine so a test can pass a SQLite engine and
run the real routers unchanged; production calls it with no argument and gets the
configured TimescaleDB engine. The app owns the sessionmaker on ``app.state`` and
disposes the engine on shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from provenance import __version__
from provenance.api.errors import install_error_handlers
from provenance.api.logging import RequestContextMiddleware
from provenance.api.routers import (
    audit,
    defects,
    events,
    export,
    meta,
    quality,
    readings,
    stations,
    trust,
)
from provenance.config.settings import get_settings
from provenance.io.db.engine import make_engine, make_sessionmaker

_ROUTERS = (
    meta.router,
    stations.router,
    readings.router,
    defects.router,
    trust.router,
    quality.router,
    events.router,
    audit.router,
    export.router,
)

_DESCRIPTION = (
    "The operator-facing trust layer for the Green Sentinel environmental sensor "
    "network. Every trust score carries its component breakdown and at least one "
    "reason code; no endpoint returns a bare number."
)


def create_app(engine: AsyncEngine | None = None) -> FastAPI:
    owns_engine = engine is None
    engine = engine or make_engine()
    sessionmaker = make_sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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

    # The dashboard runs on its own origin, so without CORS every browser request
    # fails preflight and the screens render empty against a perfectly healthy API.
    # An explicit allow-list, never "*": the API authenticates with a header key,
    # and a wildcard origin would let any page spend an operator's credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list(),
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["X-API-Key", "Accept", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    for router in _ROUTERS:
        app.include_router(router)
    return app
