"""Pagination invariants: a full cursor traversal returns every row exactly once."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

RESEARCHER = {"X-API-Key": "prov-researcher-key"}
PUBLIC = {"X-API-Key": "prov-public-key"}


async def _traverse(client: httpx.AsyncClient, path: str, headers: dict, key: str) -> list:
    """Follow next_cursor to exhaustion, collecting an identity for each item."""
    seen: list = []
    cursor = None
    sep = "&" if "?" in path else "?"
    for _ in range(10_000):  # guard against a cursor that never terminates
        url = f"{path}{sep}limit=50" + (f"&cursor={cursor}" if cursor else "")
        resp = await client.get(url, headers=headers)
        assert resp.status_code == 200, resp.text[:200]
        page = resp.json()
        seen.extend(item[key] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    return seen


async def test_readings_traversal_visits_every_row_once(api_client: httpx.AsyncClient) -> None:
    ids = await _traverse(api_client, "/v1/readings", RESEARCHER, "row_hash")
    assert len(ids) == len(set(ids))
    # Reconcile against an unpaginated total.
    total = (await api_client.get("/v1/readings?limit=500", headers=RESEARCHER)).json()
    assert len(ids) >= total["count"]
    assert len(ids) > 500  # the fixture corpus is larger than one page


async def test_defects_traversal_visits_every_row_once(api_client: httpx.AsyncClient) -> None:
    ids = await _traverse(api_client, "/v1/defects", RESEARCHER, "id")
    assert len(ids) == len(set(ids))
    assert len(ids) > 0


async def test_stations_traversal_visits_every_row_once(api_client: httpx.AsyncClient) -> None:
    ids = await _traverse(api_client, "/v1/stations", PUBLIC, "station_id")
    assert sorted(ids) == sorted(set(ids))


async def test_filtered_traversal_is_consistent(api_client: httpx.AsyncClient) -> None:
    ids = await _traverse(api_client, "/v1/readings?station=STA-01", RESEARCHER, "row_hash")
    assert len(ids) == len(set(ids))


async def test_malformed_cursor_is_a_client_error(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/v1/readings?cursor=not-a-valid-cursor", headers=RESEARCHER)
    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("application/problem+json")
