"""The persistence layer: idempotent loading and full provenance on every row."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.io.db import models as m
from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
from provenance.io.db.loader import load_frame


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await create_all(engine)
    sm = make_sessionmaker(engine)
    async with sm() as s:
        yield s
    await engine.dispose()


async def _count(session: AsyncSession, model: type) -> int:
    return int((await session.scalar(select(func.count()).select_from(model))) or 0)


async def test_load_persists_readings_defects_and_trust(
    session: AsyncSession, synthetic_corpus: tuple
) -> None:
    frame, _ = synthetic_corpus
    report = await load_frame(session, frame, source="fixtures", path="tests/fixtures")
    assert not report.already_loaded
    assert await _count(session, m.Reading) == report.readings_inserted > 0
    assert await _count(session, m.Defect) == report.defects_inserted > 0
    assert await _count(session, m.TrustScore) == report.trust_scores_inserted > 0
    assert await _count(session, m.AuditRun) == 1
    assert await _count(session, m.IngestBatch) == 1


async def test_loading_the_same_frame_twice_is_idempotent(
    session: AsyncSession, synthetic_corpus: tuple
) -> None:
    frame, _ = synthetic_corpus
    await load_frame(session, frame, source="fixtures", path="tests/fixtures")
    before = await _count(session, m.Reading)
    report2 = await load_frame(session, frame, source="fixtures", path="tests/fixtures")
    after = await _count(session, m.Reading)
    assert report2.already_loaded is True
    assert before == after


async def test_every_reading_carries_its_ingest_batch(
    session: AsyncSession, synthetic_corpus: tuple
) -> None:
    frame, _ = synthetic_corpus
    report = await load_frame(session, frame, source="fixtures", path="tests/fixtures")
    orphans = await session.scalar(
        select(func.count())
        .select_from(m.Reading)
        .where(m.Reading.ingest_batch_id != report.ingest_batch_id)
    )
    assert orphans == 0


async def test_every_defect_carries_its_audit_run(
    session: AsyncSession, synthetic_corpus: tuple
) -> None:
    frame, _ = synthetic_corpus
    report = await load_frame(session, frame, source="fixtures", path="tests/fixtures")
    orphans = await session.scalar(
        select(func.count())
        .select_from(m.Defect)
        .where(m.Defect.audit_run_id != report.audit_run_id)
    )
    assert orphans == 0


async def test_defect_counts_flag_matches_the_registry(
    session: AsyncSession, synthetic_corpus: tuple
) -> None:
    from provenance.config import reason_codes

    frame, _ = synthetic_corpus
    await load_frame(session, frame, source="fixtures", path="tests/fixtures")
    counting = {rc.code for rc in reason_codes.defect_codes()}
    defects = (await session.scalars(select(m.Defect))).all()
    for d in defects:
        assert d.counts_toward_rate == (d.reason_code in counting)


async def test_events_have_null_verdict_until_phase_four(
    session: AsyncSession, synthetic_corpus: tuple
) -> None:
    frame, _ = synthetic_corpus
    await load_frame(session, frame, source="fixtures", path="tests/fixtures")
    events = (await session.scalars(select(m.Event))).all()
    assert events  # the fixture has notable events
    assert all(e.verdict is None for e in events)
