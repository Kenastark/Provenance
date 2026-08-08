"""Structured request logging with a per-request id.

Every request is assigned (or inherits, from an inbound ``X-Request-ID``) a request
id, stamped onto ``request.state``, echoed in the response header, and bound into a
structlog context so every log line for that request carries it. That id is the
thread tying an API access, a log line, and an RFC 7807 problem together.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("provenance.api")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, time the request, and log one structured line per call."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed")
            structlog.contextvars.clear_contextvars()
            raise
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        structlog.contextvars.clear_contextvars()
        return response
