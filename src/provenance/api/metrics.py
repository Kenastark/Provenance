"""Infra-plane monitoring: Prometheus service-health metrics (§11).

This is the *infrastructure* monitor — is the service up, how many requests, how fast,
how many errors. It is deliberately kept separate from the **model**-drift monitor
(:mod:`provenance.ops.drift`, surfaced at ``/v1/admin/model-drift``): infra health and
model health are different questions with different owners and different dashboards,
and keeping them apart is the maturity signal the phase-7 prompt asks for. Service
health scrapes here at ``/metrics``; model drift lives behind the admin dashboard.

A tiny hand-rolled registry keeps the dependency surface unchanged during the freeze —
the Prometheus text exposition format is simple enough to emit directly.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

# Latency histogram buckets, in seconds. A web API's useful range: sub-ms to a few
# seconds. Cumulative "le" (less-than-or-equal) buckets, per the Prometheus convention.
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class MetricsRegistry:
    """A minimal, thread-safe registry: request counts, a latency histogram, in-flight."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._bucket_counts: dict[tuple[str, str], list[int]] = defaultdict(
            lambda: [0] * len(_BUCKETS)
        )
        self._sum: dict[tuple[str, str], float] = defaultdict(float)
        self._count: dict[tuple[str, str], int] = defaultdict(int)
        self._in_flight = 0

    def inc_in_flight(self) -> None:
        with self._lock:
            self._in_flight += 1

    def dec_in_flight(self) -> None:
        with self._lock:
            self._in_flight -= 1

    def observe(self, method: str, path: str, status: int, duration: float) -> None:
        key = (method, path)
        with self._lock:
            self._requests[(method, path, status)] += 1
            self._sum[key] += duration
            self._count[key] += 1
            for i, edge in enumerate(_BUCKETS):
                if duration <= edge:
                    self._bucket_counts[key][i] += 1

    def render(self) -> str:
        lines: list[str] = [
            "# HELP prov_up 1 if the service is serving.",
            "# TYPE prov_up gauge",
            "prov_up 1",
            "# HELP prov_http_requests_total Total HTTP requests by method, path and status.",
            "# TYPE prov_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), n in sorted(self._requests.items()):
                lines.append(
                    f'prov_http_requests_total{{method="{method}",path="{path}",'
                    f'status="{status}"}} {n}'
                )
            lines += [
                "# HELP prov_http_requests_in_flight In-flight HTTP requests.",
                "# TYPE prov_http_requests_in_flight gauge",
                f"prov_http_requests_in_flight {self._in_flight}",
                "# HELP prov_http_request_duration_seconds Request latency histogram.",
                "# TYPE prov_http_request_duration_seconds histogram",
            ]
            for (method, path), buckets in sorted(self._bucket_counts.items()):
                cumulative = 0
                for i, edge in enumerate(_BUCKETS):
                    cumulative += buckets[i]
                    lines.append(
                        f'prov_http_request_duration_seconds_bucket{{method="{method}",'
                        f'path="{path}",le="{edge}"}} {cumulative}'
                    )
                total = self._count[(method, path)]
                lines.append(
                    f'prov_http_request_duration_seconds_bucket{{method="{method}",'
                    f'path="{path}",le="+Inf"}} {total}'
                )
                lines.append(
                    f'prov_http_request_duration_seconds_sum{{method="{method}",'
                    f'path="{path}"}} {self._sum[(method, path)]:.6f}'
                )
                lines.append(
                    f'prov_http_request_duration_seconds_count{{method="{method}",'
                    f'path="{path}"}} {total}'
                )
        return "\n".join(lines) + "\n"


REGISTRY = MetricsRegistry()


def _template(request: Request) -> str:
    """The matched route template (low cardinality), or the raw path as a fallback."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Time every request and record it, using the matched route template as the label."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path == "/metrics":
            return await call_next(request)
        REGISTRY.inc_in_flight()
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            REGISTRY.dec_in_flight()
            REGISTRY.observe(
                request.method, _template(request), status, time.perf_counter() - start
            )


async def metrics_endpoint(request: Request) -> Response:
    """The Prometheus scrape target. Unauthenticated, like the other meta probes."""
    return PlainTextResponse(REGISTRY.render(), media_type="text/plain; version=0.0.4")
