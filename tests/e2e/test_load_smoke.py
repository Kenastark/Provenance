"""Load smoke: 50 concurrent dashboard clients against the API (§ phase-7 test gate).

The dashboard opens several requests per screen and the demo may have a few operators
watching at once. This fires 50 concurrent requests across a mix of read endpoints and
asserts every one succeeds — no errors, no dropped connections under fan-out.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

pytestmark = pytest.mark.e2e

PUBLIC = {"X-API-Key": "prov-public-key"}
RESEARCHER = {"X-API-Key": "prov-researcher-key"}

# The mix of requests a dashboard makes on load.
_PATHS = [
    ("/v1/stations", PUBLIC),
    ("/v1/quality/summary", PUBLIC),
    ("/v1/events", PUBLIC),
    ("/v1/trust/STA-01", PUBLIC),
    ("/healthz", {}),
    ("/v1/defects?limit=50", RESEARCHER),
]


async def test_fifty_concurrent_clients_all_succeed(api_client: httpx.AsyncClient) -> None:
    async def _one(i: int) -> int:
        path, headers = _PATHS[i % len(_PATHS)]
        resp = await api_client.get(path, headers=headers)
        return resp.status_code

    statuses = await asyncio.gather(*[_one(i) for i in range(50)])
    assert len(statuses) == 50
    assert all(s == 200 for s in statuses), (
        f"{sum(1 for s in statuses if s != 200)}/50 requests failed: "
        f"{[s for s in statuses if s != 200][:10]}"
    )
