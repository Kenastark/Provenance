"""The auth matrix: every endpoint x every role, asserting the expected allow/deny.

Roles form a hierarchy (operator >= researcher >= public_read). Open endpoints
(health, readiness, version) need no key; public endpoints need any valid key; the
researcher-tier endpoints reject public_read.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

# tier: "open" (no key), "public" (any key), "researcher" (researcher+operator)
ENDPOINTS = [
    ("/healthz", "open"),
    ("/readyz", "open"),
    ("/version", "open"),
    ("/v1/stations", "public"),
    ("/v1/stations/STA-01", "public"),
    ("/v1/trust/STA-01", "public"),
    ("/v1/quality/summary", "public"),
    ("/v1/events", "public"),
    ("/v1/reference/bus-stops", "public"),
    ("/v1/reference/traffic-counters", "public"),
    ("/v1/readings", "researcher"),
    ("/v1/defects", "researcher"),
    ("/v1/audit/runs", "researcher"),
    ("/v1/export/audit-trail", "researcher"),
]

KEYS = {
    "none": None,
    "public_read": "prov-public-key",
    "researcher": "prov-researcher-key",
    "operator": "prov-operator-key",
}


def _expected(tier: str, role: str) -> int:
    if tier == "open":
        return 200
    if role == "none":
        return 401
    if tier == "public":
        return 200
    # researcher tier
    return 200 if role in {"researcher", "operator"} else 403


@pytest.mark.parametrize("path,tier", ENDPOINTS)
@pytest.mark.parametrize("role", list(KEYS))
async def test_auth_matrix(api_client: httpx.AsyncClient, path: str, tier: str, role: str) -> None:
    headers = {"X-API-Key": KEYS[role]} if KEYS[role] else {}
    resp = await api_client.get(path, headers=headers)
    assert resp.status_code == _expected(tier, role), (
        f"{path} as {role}: got {resp.status_code}, body {resp.text[:200]}"
    )


async def test_audit_run_detail_respects_roles(
    api_client: httpx.AsyncClient, loaded_db: dict
) -> None:
    path = f"/v1/audit/runs/{loaded_db['run_id']}"
    assert (await api_client.get(path, headers={"X-API-Key": "prov-public-key"})).status_code == 403
    assert (
        await api_client.get(path, headers={"X-API-Key": "prov-researcher-key"})
    ).status_code == 200
    assert (await api_client.get(path)).status_code == 401


async def test_denials_are_rfc7807_problems(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/v1/readings")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 401
    assert body["title"] == "Unauthorized"
    assert "request_id" in body
