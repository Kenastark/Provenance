"""Adjudication verdicts are written back onto the stored events end-to-end.

The default fixture corpus carries no wind, so every event honestly adjudicates to
AMBIGUOUS (a plume cannot be assessed without wind) and routes to review — which is
exactly the graceful, non-guessing behaviour the phase promises. What this proves is
the *wiring*: the audit's null verdicts become real, explained verdicts the API can
serve, with the evidence bundle attached.
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import select

from provenance.fixtures.generator import generate, station_locations
from provenance.graph.persist import NOT_APPLICABLE_KEY, adjudicate_stored_events
from provenance.io.db import models as m
from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
from provenance.io.db.loader import load_frame
from provenance.io.loaders import StationLocation
from provenance.schema import canonical as C

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
            assert updated.adjudicated >= 1
            assert updated.total == len(before)

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


async def test_an_event_with_no_reading_records_why_rather_than_reading_as_pending(
    tmp_path,
) -> None:
    """A null verdict must not be ambiguous about its own meaning.

    An event whose own cell has no reading has no rise for the wind to carry, so the
    plume test cannot apply. It keeps a null verdict - folding it into AMBIGUOUS would
    claim we are unsure when we are not - but it gains a recorded reason, so the
    dashboard can tell "considered, does not apply" from "not adjudicated yet".
    """
    engine, sm, frame, meta = await _loaded_session(tmp_path)
    try:
        async with sm() as session:
            events = (await session.scalars(select(m.Event))).all()
            assert events
            # Store an event on a cell the frame has no reading for: same station and
            # parameter as a real one, an hour outside the corpus window. Derived from
            # the frame, so no station or code is named here.
            template = events[0]
            session.add(
                m.Event(
                    audit_run_id=template.audit_run_id,
                    rank=len(events) + 1,
                    category="communication_outage",
                    reason_code=template.reason_code,
                    station_id=template.station_id,
                    parameter=template.parameter,
                    timestamp_utc=pd.Timestamp(frame[C.TIMESTAMP].max()) + pd.Timedelta(days=400),
                    headline="synthetic gap with no reading behind it",
                    severity="high",
                    evidence={"missing_ticks": 3},
                )
            )
            await session.commit()

        async with sm() as session:
            result = await adjudicate_stored_events(session, frame, dict(meta))
            assert result.not_applicable >= 1

        async with sm() as session:
            gap = (
                await session.scalars(
                    select(m.Event).where(
                        m.Event.headline == "synthetic gap with no reading behind it"
                    )
                )
            ).one()
            assert gap.verdict is None, "an outage is not an AMBIGUOUS call"
            record = gap.evidence[NOT_APPLICABLE_KEY]
            assert record["basis"] == "no_reading_at_event_time"
            assert "no rise" in record["reason"]
            assert "adjudication" not in gap.evidence
    finally:
        await engine.dispose()


async def test_a_recorded_non_applicability_clears_once_the_event_becomes_adjudicable(
    tmp_path,
) -> None:
    """The record is state, not a label: it must not outlive the condition that set it."""
    engine, sm, frame, meta = await _loaded_session(tmp_path)
    try:
        async with sm() as session:
            event = (await session.scalars(select(m.Event))).first()
            assert event is not None
            stale = dict(event.evidence or {})
            stale[NOT_APPLICABLE_KEY] = {"basis": "no_reading_at_event_time", "reason": "stale"}
            event.evidence = stale
            await session.commit()
            target_id = event.id

        async with sm() as session:
            await adjudicate_stored_events(session, frame, dict(meta))

        async with sm() as session:
            refreshed = (
                await session.scalars(select(m.Event).where(m.Event.id == target_id))
            ).one()
            assert refreshed.verdict is not None
            assert NOT_APPLICABLE_KEY not in refreshed.evidence
    finally:
        await engine.dispose()
