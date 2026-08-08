"""RFC 7807 problem responses.

Every error the API returns is an ``application/problem+json`` document with the
same shape, so a client parses one error format everywhere. The request id is
echoed into every problem so a failure in a log line and a failure a user saw are
the same incident.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"

_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
}


class ProblemException(Exception):
    """Raise to return a specific RFC 7807 problem."""

    def __init__(self, status: int, detail: str, *, type_: str = "about:blank") -> None:
        self.status = status
        self.detail = detail
        self.type_ = type_
        super().__init__(detail)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def problem_response(
    request: Request,
    status: int,
    detail: str,
    *,
    type_: str = "about:blank",
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": type_,
        "title": _TITLES.get(status, "Error"),
        "status": status,
        "detail": detail,
        "instance": str(request.url.path),
        "request_id": _request_id(request),
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=status,
        content=body,
        media_type=PROBLEM_MEDIA_TYPE,
        headers={"X-Request-ID": _request_id(request) or ""},
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register the handlers that turn every error into a problem document."""

    @app.exception_handler(ProblemException)
    async def _problem(request: Request, exc: ProblemException) -> JSONResponse:
        return problem_response(request, exc.status, exc.detail, type_=exc.type_)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem_response(request, exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(
            request,
            422,
            "Request parameters failed validation.",
            extra={"errors": exc.errors()},
        )

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        # A cursor whose payload survives base64/JSON decoding but is not a valid
        # ordering key (e.g. a non-ISO timestamp) surfaces here as a client error,
        # not a server fault — again important under the schemathesis fuzz.
        return problem_response(request, 400, "A request value could not be interpreted.")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        return problem_response(request, 500, "An unexpected error occurred.")
