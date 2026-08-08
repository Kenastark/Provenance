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

    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    for router in _ROUTERS:
        app.include_router(router)
    return app
