"""Monitoring: the infra plane (/metrics) and the model plane (/v1/admin/model-drift)."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

ADMIN = {"X-API-Key": "prov-admin-key"}
OPERATOR = {"X-API-Key": "prov-operator-key"}
PUBLIC = {"X-API-Key": "prov-public-key"}


async def test_metrics_endpoint_is_prometheus_text_and_needs_no_key(
    ops_client: httpx.AsyncClient,
) -> None:
    # Generate some traffic first so the counters are non-trivial.
    await ops_client.get("/v1/stations", headers=PUBLIC)
    await ops_client.get("/healthz")
    resp = await ops_client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "prov_up 1" in body
    assert "prov_http_requests_total" in body
    assert "prov_http_request_duration_seconds_bucket" in body


async def test_model_drift_is_admin_only_and_separates_planes(
    ops_client: httpx.AsyncClient,
) -> None:
    assert (await ops_client.get("/v1/admin/model-drift", headers=OPERATOR)).status_code == 403
    resp = await ops_client.get("/v1/admin/model-drift", headers=ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["plane"] == "model"
    # The four model-drift categories are all present (some may be empty pending training).
    assert "defect_rate_by_station" in body
    assert "deweather_r2" in body
    assert "conformal_coverage" in body
    assert "fault_confusion" in body
    # Defect-rate drift is always computable from the audit runs.
    assert body["defect_rate_by_station"], "at least one station should have a drift series"
