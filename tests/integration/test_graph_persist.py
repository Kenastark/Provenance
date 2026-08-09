"""Adjudication verdicts are written back onto the stored events end-to-end.

The default fixture corpus carries no wind, so every event honestly adjudicates to
AMBIGUOUS (a plume cannot be assessed without wind) and routes to review — which is
exactly the graceful, non-guessing behaviour the phase promises. What this proves is
the *wiring*: the audit's null verdicts become real, explained verdicts the API can
serve, with the evidence bundle attached.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from provenance.fixtures.generator import generate, station_locations
from provenance.graph.persist import adjudicate_stored_events
from provenance.io.db import models as m
from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
from provenance.io.db.loader import load_frame
from provenance.io.loaders import StationLocation

pytestmark = pytest.mark.asyncio


async def _loaded_session(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'adj.db'}"
    engine = make_engine(url)
    await create_all(engine)
    sm = make_sessionmaker(engine)
    frame, _ = generate(n_stations=6)
    locs = station_locations(6)
    meta = {
        sid: StationLocation(station_id=sid, name=spec["name"], lat=spec["lat"], lon=spec["lon"])
        for sid, spec in locs.items()
    }
    async with sm() as session:
        await load_frame(session, frame, source="fixtures", path="tests", station_meta=meta)
    return engine, sm, frame, meta


async def test_verdicts_populate_on_stored_events(tmp_path) -> None:
    engine, sm, frame, meta = await _loaded_session(tmp_path)
    try:
        async with sm() as session:
            before = (await session.scalars(select(m.Event))).all()
            assert before, "the audit should have stored some notable events"
            assert all(e.verdict is None for e in before)

            updated = await adjudicate_stored_events(session, frame, dict(meta))
            assert updated >= 1

        async with sm() as session:
            after = (await session.scalars(select(m.Event))).all()
            adjudicated = [e for e in after if e.verdict is not None]
            assert adjudicated, "verdicts should now be populated"
            for event in adjudicated:
                assert event.verdict in {"GENUINE_EVENT", "LIKELY_FAULT", "AMBIGUOUS"}
                # No wind in this corpus ⇒ the honest verdict is AMBIGUOUS.
                assert event.verdict == "AMBIGUOUS"
                bundle = event.evidence["adjudication"]
                assert bundle["verdict"] == event.verdict
                assert bundle["routes_to_review"] is True
                assert "reason_codes" in bundle["evidence"]
    finally:
        await engine.dispose()


async def test_adjudication_is_idempotent(tmp_path) -> None:
    engine, sm, frame, meta = await _loaded_session(tmp_path)
    try:
        async with sm() as session:
            first = await adjudicate_stored_events(session, frame, dict(meta))
        async with sm() as session:
            second = await adjudicate_stored_events(session, frame, dict(meta))
        assert first == second
    finally:
        await engine.dispose()
