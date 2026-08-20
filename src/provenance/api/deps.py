"""Request dependencies: the database session and role enforcement.

The sessionmaker lives on ``app.state`` so a test can build the app against a
SQLite engine and the same routers run unchanged. ``require(role)`` is the single
gate every data endpoint declares; it turns a missing or wrong key into an RFC 7807
problem, and returns the caller's resolved role to the handler.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from provenance.api.auth import Role, api_key_header, role_for_key, role_satisfies
from provenance.api.errors import ProblemException


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


def get_data_raw(request: Request) -> Path:
    """The raw-data root the reference endpoints read file-drops from.

    ``app.state.data_raw`` (set by ``create_app``) lets a test point this at an
    isolated fixture directory the same way ``engine`` isolates the database,
    rather than every test racing the developer's real ``data/raw``."""
    return Path(request.app.state.data_raw)


def require(required: Role) -> Callable[..., Coroutine[Any, Any, Role]]:
    """Dependency: require at least ``required`` access, returning the caller's role."""

    async def _dependency(key: str | None = Depends(api_key_header)) -> Role:
        role = role_for_key(key)
        if role is None:
            raise ProblemException(
                401,
                "A valid X-API-Key header is required.",
                type_="https://provenance.example/problems/unauthorized",
            )
        if not role_satisfies(role, required):
            raise ProblemException(
                403,
                f"Role '{role}' is not permitted to access this resource (requires '{required}').",
                type_="https://provenance.example/problems/forbidden",
            )
        return role

    return _dependency
