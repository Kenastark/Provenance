"""The regulator-facing audit-trail export: reproducible and reconciled."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

RESEARCHER = {"X-API-Key": "prov-researcher-key"}


async def test_csv_export_is_byte_for_byte_reproducible(
    api_client: httpx.AsyncClient, loaded_db: dict
) -> None:
    run_id = loaded_db["run_id"]
    url = f"/v1/export/audit-trail?format=csv&run_id={run_id}"
    first = await api_client.get(url, headers=RESEARCHER)
    second = await api_client.get(url, headers=RESEARCHER)
    assert first.status_code == 200
    assert first.text == second.text  # byte-for-byte stable
    assert first.headers["content-type"].startswith("text/csv")


async def test_csv_row_count_reconciles_with_the_defects_table(
    api_client: httpx.AsyncClient, loaded_db: dict
) -> None:
    run_id = loaded_db["run_id"]
    csv_resp = await api_client.get(
        f"/v1/export/audit-trail?format=csv&run_id={run_id}", headers=RESEARCHER
    )
    # One header line, then one row per defect, then the structural exclusions.
    lines = [line for line in csv_resp.text.split("\n") if line]
    defect_rows = [line for line in lines[1:] if line.startswith("defect,")]
    header_count = int(csv_resp.headers["X-Defect-Row-Count"])
    assert len(defect_rows) == header_count

    # Reconcile against the defects endpoint total for the same run.
    total = 0
    cursor = None
    while True:
        u = "/v1/defects?limit=500" + (f"&cursor={cursor}" if cursor else "")
        page = (await api_client.get(u, headers=RESEARCHER)).json()
        total += sum(1 for d in page["items"] if d["audit_run_id"] == run_id)
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert header_count == total


async def test_json_export_carries_the_defect_rate_definition(
    api_client: httpx.AsyncClient, loaded_db: dict
) -> None:
    run_id = loaded_db["run_id"]
    body = (
        await api_client.get(
            f"/v1/export/audit-trail?format=json&run_id={run_id}", headers=RESEARCHER
        )
    ).json()
    assert "defect rate" in body["definition"]
    assert body["reconciliation"]["n_defect_rows"] == len(body["defects"])
    assert body["structural_exclusions"]  # the fixture has structural absences


async def test_export_unknown_run_is_404(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get(
        "/v1/export/audit-trail?run_id=ar_does_not_exist", headers=RESEARCHER
    )
    assert resp.status_code == 404
