"""Endpoint contract: shapes, the trust guarantee, and cross-cutting concerns."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

PUBLIC = {"X-API-Key": "prov-public-key"}
RESEARCHER = {"X-API-Key": "prov-researcher-key"}


async def test_healthz(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_readyz_reports_database(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/readyz")).json()
    assert body["database"] == "ok"


async def test_version_carries_provenance(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/version")).json()
    assert body["config_hash"] and body["trust_config_hash"]
    assert "trust_score" in body["model_versions"]


async def test_every_request_gets_a_request_id(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/healthz")
    assert resp.headers.get("X-Request-ID")


async def test_trust_response_always_has_components_and_reason_codes(
    api_client: httpx.AsyncClient,
) -> None:
    body = (await api_client.get("/v1/trust/STA-01", headers=PUBLIC)).json()
    assert len(body["components"]) == 4
    assert body["reason_codes"]
    assert body["risk"]["population_exposure_stubbed"] is True
    # No bare number: the trust value never appears without its breakdown.
    assert "trust" in body and "components" in body


async def test_trust_series_is_paginated_and_explained(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/v1/trust/STA-01?series=true", headers=PUBLIC)).json()
    assert "items" in body
    for item in body["items"]:
        assert item["components"] and item["reason_codes"]


async def test_trust_series_is_a_real_trajectory(api_client: httpx.AsyncClient) -> None:
    # Not a single point: the loader scores each station daily across the window, so
    # the series carries multiple ascending, distinct, fully-explained timestamps.
    body = (await api_client.get("/v1/trust/STA-01?series=true&limit=500", headers=PUBLIC)).json()
    stamps = [item["timestamp_utc"] for item in body["items"]]
    assert len(stamps) > 1, "trust series should be a trajectory, not one point"
    assert stamps == sorted(stamps)
    assert len(stamps) == len(set(stamps))
    assert stamps[-1] == "2026-05-14T23:00:00"  # anchored on the last reading
    for item in body["items"]:
        assert len(item["components"]) == 4 and item["reason_codes"]


async def test_trust_unknown_station_is_404_problem(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/v1/trust/NOPE", headers=PUBLIC)
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_quality_summary_shape(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/v1/quality/summary", headers=PUBLIC)).json()
    assert body["stations"]
    row = body["stations"][0]
    assert {"station_id", "trust", "health", "flag_count"} <= set(row)


async def test_quality_summary_reports_last_reading_time(api_client: httpx.AsyncClient) -> None:
    # last_reading_at must be the real max reading time, not null. The seeded corpus
    # runs 14 hourly days from 2026-05-01, so the last hour is 2026-05-14T23:00:00.
    body = (await api_client.get("/v1/quality/summary", headers=PUBLIC)).json()
    by_station = {r["station_id"]: r for r in body["stations"]}
    assert all(r["last_reading_at"] is not None for r in body["stations"])
    assert by_station["STA-01"]["last_reading_at"] == "2026-05-14T23:00:00"


async def test_readings_quality_flagged_annotates_defect_cells(
    api_client: httpx.AsyncClient,
) -> None:
    # STA-03 PM10 carries injected physical-max exceedances (R07) in the corpus.
    resp = await api_client.get(
        "/v1/readings?station=STA-03&parameter=PM10&quality_flagged=true&limit=500",
        headers=RESEARCHER,
    )
    items = resp.json()["items"]
    assert any(item.get("reason_codes") for item in items)
    assert any("R07" in (item.get("reason_codes") or []) for item in items)


async def test_events_expose_a_null_verdict(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/v1/events", headers=PUBLIC)).json()
    assert body["items"]
    assert all(item["verdict"] is None for item in body["items"])


async def test_defect_filter_by_code(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/v1/defects?code=R07", headers=RESEARCHER)).json()
    assert body["items"]
    assert all(item["reason_code"] == "R07" for item in body["items"])


async def test_openapi_is_served(api_client: httpx.AsyncClient) -> None:
    schema = (await api_client.get("/openapi.json")).json()
    assert schema["info"]["title"] == "Provenance API"
    assert "/v1/trust/{station_id}" in schema["paths"]
