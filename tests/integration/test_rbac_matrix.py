"""The full RBAC matrix (§11): every endpoint × every role.

Four roles now (``public_read`` < ``researcher`` < ``operator`` < ``admin``) across
the read product, the regulator export, the operational surface, and the admin
dashboard. For each endpoint the test asserts the exact allow/deny for all five caller
states (no key + the four roles). The rule is uniform: an unauthenticated caller gets
401, an authenticated caller below the required tier gets 403, and a caller at or above
it gets through (any non-auth status).
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

# tier → the ranked roles permitted. "open" needs no key at all.
TIER_ORDER = ["public_read", "researcher", "operator", "admin"]
TIER_MIN_INDEX = {"public": 0, "researcher": 1, "operator": 2, "admin": 3}

# (method, path, tier, body-or-None)
ENDPOINTS: list[tuple[str, str, str, dict | None]] = [
    ("GET", "/healthz", "open", None),
    ("GET", "/readyz", "open", None),
    ("GET", "/version", "open", None),
    ("GET", "/v1/stations", "public", None),
    ("GET", "/v1/stations/STA-01", "public", None),
    ("GET", "/v1/trust/STA-01", "public", None),
    ("GET", "/v1/quality/summary", "public", None),
    ("GET", "/v1/events", "public", None),
    ("GET", "/v1/readings", "researcher", None),
    ("GET", "/v1/defects", "researcher", None),
    ("GET", "/v1/audit/runs", "researcher", None),
    ("GET", "/v1/export/audit-trail", "researcher", None),
    ("GET", "/v1/maintenance", "operator", None),
    ("GET", "/v1/alerts", "operator", None),
    ("POST", "/v1/maintenance/rebuild", "operator", {}),
    ("POST", "/v1/decision/signoff", "operator", {"event_id": 1, "channel": "webhook"}),
    (
        "POST",
        "/v1/decision/dispatch",
        "operator",
        {"event_id": 1, "channel": "webhook", "signoff_id": "so_x"},
    ),
    ("GET", "/v1/admin/status", "admin", None),
    ("POST", "/v1/admin/retrain", "admin", {"target": "deweather"}),
]

KEYS = {
    "none": None,
    "public_read": "prov-public-key",
    "researcher": "prov-researcher-key",
    "operator": "prov-operator-key",
    "admin": "prov-admin-key",
}


def _permitted(tier: str, role: str) -> bool:
    if tier == "open":
        return True
    if role == "none":
        return False
    return TIER_ORDER.index(role) >= TIER_MIN_INDEX[tier]


@pytest.mark.parametrize("method,path,tier,body", ENDPOINTS)
@pytest.mark.parametrize("role", list(KEYS))
async def test_rbac_matrix(
    rbac_client: httpx.AsyncClient,
    method: str,
    path: str,
    tier: str,
    body: dict | None,
    role: str,
) -> None:
    headers = {"X-API-Key": KEYS[role]} if KEYS[role] else {}
    if method == "GET":
        resp = await rbac_client.get(path, headers=headers)
    else:
        resp = await rbac_client.post(path, headers=headers, json=body or {})

    if _permitted(tier, role):
        # Authorised: never an auth rejection (the body may still be 422/404 etc.).
        assert resp.status_code not in (401, 403), f"{method} {path} as {role}: {resp.text[:160]}"
    elif role == "none":
        assert resp.status_code == 401, f"{method} {path} as none: {resp.status_code}"
    else:
        assert resp.status_code == 403, f"{method} {path} as {role}: {resp.status_code}"
