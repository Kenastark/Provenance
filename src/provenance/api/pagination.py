"""Opaque cursor pagination.

Every list endpoint returns a ``Page`` with a ``next_cursor`` that encodes the
ordering key of the last row returned. The cursor is a base64 of a JSON tuple —
opaque to clients, cheap to decode — so a full traversal (follow ``next_cursor``
until it is null) visits every row exactly once, with no offset drift as rows are
appended. The invariant is asserted by ``tests`` for each endpoint.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from pydantic import BaseModel

MAX_LIMIT = 500
DEFAULT_LIMIT = 100


def encode_cursor(key: Any) -> str:
    """Encode an ordering key (scalar or tuple) into an opaque cursor string."""
    raw = json.dumps(key, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str | None) -> Any:
    """Decode a cursor back into its ordering key, or ``None`` for the first page.

    A malformed cursor is a client error (400), not a server fault — important
    under the schemathesis fuzz, which sends arbitrary cursor strings.
    """
    if not cursor:
        return None
    from provenance.api.errors import ProblemException

    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        return json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ProblemException(400, f"Malformed pagination cursor: {cursor!r}.") from exc


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


class Page[T](BaseModel):
    """A page of results plus the cursor for the next page (null when exhausted)."""

    items: list[T]
    next_cursor: str | None = None
    count: int
