"""The completed regulatory export end to end (§2, phase 7).

Verification hash reproducible and reconciled against the database; the sign-off
appendix does not disturb it; the PDF summary is a valid, reproducible document.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

RESEARCHER = {"X-API-Key": "prov-researcher-key"}
OPERATOR = {"X-API-Key": "prov-operator-key"}


async def test_verification_hash_is_reproducible_and_in_the_header(
    ops_client: httpx.AsyncClient,
) -> None:
    url = "/v1/export/audit-trail?format=json"
    first = await ops_client.get(url, headers=RESEARCHER)
    second = await ops_client.get(url, headers=RESEARCHER)
    assert first.status_code == 200
    h1 = first.json()["verification_hash"]
    h2 = second.json()["verification_hash"]
    assert h1 == h2
    assert first.headers["X-Verification-Hash"] == h1


async def test_reading_accounting_reconciles_against_the_database(
    ops_client: httpx.AsyncClient,
) -> None:
    body = (await ops_client.get("/v1/export/audit-trail?format=json", headers=RESEARCHER)).json()
    assert body["accounting"]["n_readings"] > 0
    assert body["reconciliation"]["n_defect_rows"] == len(body["defects"])

    # The exported reading count matches a full traversal of the readings endpoint.
    total = 0
    cursor = None
    while True:
        u = "/v1/readings?limit=500" + (f"&cursor={cursor}" if cursor else "")
        page = (await ops_client.get(u, headers=RESEARCHER)).json()
        total += page["count"]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert body["accounting"]["n_readings"] == total


async def test_signoff_in_period_appears_but_does_not_move_the_hash(
    ops_client: httpx.AsyncClient,
) -> None:
    before = (await ops_client.get("/v1/export/audit-trail?format=json", headers=RESEARCHER)).json()
    # Record a sign-off for the first event, changing the appendix but not the record.
    event_id = (
        await ops_client.get("/v1/events", headers={"X-API-Key": "prov-public-key"})
    ).json()["items"][0]["id"]
    signoff = await ops_client.post(
        "/v1/decision/signoff",
        headers=OPERATOR,
        json={"event_id": event_id, "channel": "email", "operator": "op-1"},
    )
    assert signoff.status_code == 200

    after = (await ops_client.get("/v1/export/audit-trail?format=json", headers=RESEARCHER)).json()
    assert len(after["signoffs"]) == len(before["signoffs"]) + 1
    assert after["verification_hash"] == before["verification_hash"]


async def test_pdf_summary_is_valid(ops_client: httpx.AsyncClient) -> None:
    resp = await ops_client.get("/v1/export/audit-trail?format=pdf", headers=RESEARCHER)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF-1.4")
    assert resp.content.rstrip().endswith(b"%%EOF")
    assert resp.headers["X-Verification-Hash"].encode() in resp.content
