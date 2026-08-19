"""The human sign-off gate and idempotent dispatch, end to end (§2).

Covers the runtime half of the guarantee the static call-graph test pins: a dispatch
refuses to send without a valid sign-off, an expired sign-off cannot authorise one,
and a retry — sequential or concurrent — never sends twice.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from provenance.api.decision import channels, gate, signoff
from provenance.io.db import models as m
from provenance.io.db.engine import make_engine, make_sessionmaker

pytestmark = pytest.mark.integration

OPERATOR = {"X-API-Key": "prov-operator-key"}
PUBLIC = {"X-API-Key": "prov-public-key"}


async def _first_event_id(client: httpx.AsyncClient) -> int:
    resp = await client.get("/v1/events", headers=PUBLIC)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items, "the fixture corpus should raise at least one candidate event"
    return items[0]["id"]


async def _make_signoff(client: httpx.AsyncClient, event_id: int, channel: str = "webhook") -> str:
    resp = await client.post(
        "/v1/decision/signoff",
        headers=OPERATOR,
        json={"event_id": event_id, "channel": channel, "operator": "op-1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["signoff_id"]


async def test_dispatch_without_a_signoff_is_refused(ops_client: httpx.AsyncClient) -> None:
    event_id = await _first_event_id(ops_client)
    resp = await ops_client.post(
        "/v1/decision/dispatch",
        headers=OPERATOR,
        json={"event_id": event_id, "channel": "webhook", "signoff_id": "so_does_not_exist"},
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_signoff_then_dispatch_sends_once(ops_client: httpx.AsyncClient) -> None:
    channels.OUTBOX.clear()
    event_id = await _first_event_id(ops_client)
    signoff_id = await _make_signoff(ops_client, event_id)
    resp = await ops_client.post(
        "/v1/decision/dispatch",
        headers=OPERATOR,
        json={"event_id": event_id, "channel": "webhook", "signoff_id": signoff_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "sent"
    assert body["idempotent"] is False
    assert body["receipt"] is not None
    assert len(channels.OUTBOX) == 1


async def test_retry_is_idempotent_and_does_not_resend(ops_client: httpx.AsyncClient) -> None:
    channels.OUTBOX.clear()
    event_id = await _first_event_id(ops_client)
    signoff_id = await _make_signoff(ops_client, event_id)
    payload = {"event_id": event_id, "channel": "webhook", "signoff_id": signoff_id}

    first = (await ops_client.post("/v1/decision/dispatch", headers=OPERATOR, json=payload)).json()
    second = (await ops_client.post("/v1/decision/dispatch", headers=OPERATOR, json=payload)).json()

    assert first["dispatch_id"] == second["dispatch_id"]
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert len(channels.OUTBOX) == 1  # the retry did not send again


async def test_concurrent_dispatch_sends_once(ops_db: dict[str, str]) -> None:
    channels.OUTBOX.clear()
    engine = make_engine(ops_db["url"])
    sm = make_sessionmaker(engine)
    try:
        # Pick an event and record a sign-off up front.
        async with sm() as s:
            event = (await s.scalars(select(m.Event).limit(1))).first()
            assert event is not None
            token = await signoff.create_signoff(
                s,
                event_id=event.id,
                channel="webhook",
                operator="op-1",
                evidence={"seen": True},
                model_version="trust=v1",
            )
            event_id, signoff_id = event.id, token.id

        async def _one() -> gate.DispatchResult:
            async with sm() as s:
                return await gate.dispatch(
                    s, event_id=event_id, channel="webhook", signoff_id=signoff_id
                )

        results = await asyncio.gather(_one(), _one(), _one())

        # Exactly one real send; all three resolve to the same dispatch row.
        assert len(channels.OUTBOX) == 1
        assert len({r.dispatch_id for r in results}) == 1
        assert sum(1 for r in results if not r.idempotent) == 1

        async with sm() as s:
            n_rows = await s.scalar(
                select(func.count())
                .select_from(m.Dispatch)
                .where(
                    m.Dispatch.idempotency_key
                    == gate.idempotency_key(event_id, "webhook", signoff_id)
                )
            )
        assert n_rows == 1
    finally:
        await engine.dispose()


async def test_expired_signoff_cannot_authorise_a_dispatch(ops_db: dict[str, str]) -> None:
    channels.OUTBOX.clear()
    engine = make_engine(ops_db["url"])
    sm = make_sessionmaker(engine)
    try:
        async with sm() as s:
            event = (await s.scalars(select(m.Event).limit(1))).first()
            assert event is not None
            token = await signoff.create_signoff(
                s,
                event_id=event.id,
                channel="webhook",
                operator="op-1",
                evidence={"seen": True},
                model_version="trust=v1",
                ttl_seconds=1,
            )
            future = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)
            with pytest.raises(signoff.SignoffInvalid):
                await gate.dispatch(
                    s,
                    event_id=event.id,
                    channel="webhook",
                    signoff_id=token.id,
                    now=future,
                )
        assert len(channels.OUTBOX) == 0  # nothing was sent
    finally:
        await engine.dispose()
