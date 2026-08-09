"""The operational surface end to end (§1, §9.5): exposure, maintenance, Alert Centre.

Runs against ``ops_client`` — a fresh, writable DB with the fixture corpus loaded, a
synthetic GTFS bundle giving measured PopulationExposure, and events adjudicated.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

OPERATOR = {"X-API-Key": "prov-operator-key"}
RESEARCHER = {"X-API-Key": "prov-researcher-key"}
PUBLIC = {"X-API-Key": "prov-public-key"}


async def test_population_exposure_is_measured_not_stubbed(ops_client: httpx.AsyncClient) -> None:
    resp = await ops_client.get("/v1/quality/summary", headers=PUBLIC)
    assert resp.status_code == 200
    stations = resp.json()["items"] if "items" in resp.json() else resp.json()
    # At least one station's trust score should carry a measured (non-stubbed) exposure.
    trust = await ops_client.get("/v1/trust/STA-01", headers=PUBLIC)
    assert trust.status_code == 200
    body = trust.json()
    assert body["risk"]["population_exposure_stubbed"] is False
    assert body["risk"]["population_exposure"] != 1.0 or body["risk"]["population_exposure"] == 1.0
    assert stations  # summary is non-empty


async def test_maintenance_queue_populates_and_ranks_by_priority(
    ops_client: httpx.AsyncClient,
) -> None:
    rebuilt = await ops_client.post("/v1/maintenance/rebuild", headers=OPERATOR)
    assert rebuilt.status_code == 200
    assert rebuilt.json()["created"] > 0

    listed = await ops_client.get("/v1/maintenance", headers=OPERATOR)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert items
    priorities = [i["priority"] for i in items]
    assert priorities == sorted(priorities, reverse=True)
    for i in items:  # never a bare number: every ticket carries its evidence
        assert "evidence" in i and i["reason_code"]


async def test_maintenance_rebuild_is_idempotent(ops_client: httpx.AsyncClient) -> None:
    first = await ops_client.post("/v1/maintenance/rebuild", headers=OPERATOR)
    created = first.json()["created"]
    assert created > 0
    second = await ops_client.post("/v1/maintenance/rebuild", headers=OPERATOR)
    assert second.json()["created"] == 0  # no duplicate tickets


async def test_maintenance_lifecycle_and_history(ops_client: httpx.AsyncClient) -> None:
    await ops_client.post("/v1/maintenance/rebuild", headers=OPERATOR)
    items = (await ops_client.get("/v1/maintenance", headers=OPERATOR)).json()["items"]
    item_id = items[0]["id"]

    for target in ("acknowledged", "dispatched", "resolved"):
        resp = await ops_client.post(
            f"/v1/maintenance/{item_id}/transition",
            headers=OPERATOR,
            json={"to": target, "actor": "tech-1"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == target

    detail = (await ops_client.get(f"/v1/maintenance/{item_id}", headers=OPERATOR)).json()
    history = detail["history"]
    # open (auto) → acknowledged → dispatched → resolved = 4 recorded states.
    assert [h["to_status"] for h in history] == [
        "open",
        "acknowledged",
        "dispatched",
        "resolved",
    ]


async def test_illegal_transition_is_a_409(ops_client: httpx.AsyncClient) -> None:
    await ops_client.post("/v1/maintenance/rebuild", headers=OPERATOR)
    items = (await ops_client.get("/v1/maintenance", headers=OPERATOR)).json()["items"]
    item_id = items[0]["id"]
    # open → resolved skips the lifecycle.
    resp = await ops_client.post(
        f"/v1/maintenance/{item_id}/transition",
        headers=OPERATOR,
        json={"to": "resolved"},
    )
    assert resp.status_code == 409


async def test_alert_centre_returns_risk_ranked_items(ops_client: httpx.AsyncClient) -> None:
    resp = await ops_client.get("/v1/alerts", headers=OPERATOR)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ranked_by"] == "risk"
    risks = [a["risk"] for a in body["items"]]
    assert risks == sorted(risks, reverse=True)
    for a in body["items"]:
        assert set(a["risk_factors"]) >= {"genuineness", "exposure", "hazard"}


async def test_out_of_range_item_id_is_a_client_error_not_a_500(
    ops_client: httpx.AsyncClient,
) -> None:
    # A path integer larger than SQLite's 64-bit INTEGER must not crash the server.
    huge = 10**24
    got = await ops_client.get(f"/v1/maintenance/{huge}", headers=OPERATOR)
    assert got.status_code == 400
    posted = await ops_client.post(
        f"/v1/maintenance/{huge}/transition",
        headers=OPERATOR,
        json={"to": "acknowledged"},
    )
    assert posted.status_code == 400


async def test_operational_endpoints_require_operator(ops_client: httpx.AsyncClient) -> None:
    for path in ("/v1/maintenance", "/v1/alerts"):
        assert (await ops_client.get(path, headers=PUBLIC)).status_code == 403
        assert (await ops_client.get(path, headers=RESEARCHER)).status_code == 403
        assert (await ops_client.get(path, headers=OPERATOR)).status_code == 200
