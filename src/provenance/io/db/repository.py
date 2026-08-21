"""Read queries for the API, all keyset-paginated.

Every list query orders by a stable, unique key and takes an optional ``after``
tuple decoded from the request cursor, so a full traversal returns every row
exactly once even as rows are added. The API layer owns cursor encoding; this
layer owns the SQL.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.io.db import models as m

if TYPE_CHECKING:
    import pandas as pd


async def get_station(session: AsyncSession, station_id: str) -> m.Station | None:
    return await session.get(m.Station, station_id)


async def list_stations(
    session: AsyncSession, *, limit: int, after: str | None
) -> Sequence[m.Station]:
    stmt = select(m.Station).order_by(m.Station.station_id).limit(limit)
    if after is not None:
        stmt = stmt.where(m.Station.station_id > after)
    return (await session.scalars(stmt)).all()


async def list_readings(
    session: AsyncSession,
    *,
    limit: int,
    after: tuple[str, str] | None,
    station_id: str | None = None,
    parameter: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Sequence[m.Reading]:
    stmt = select(m.Reading).order_by(m.Reading.timestamp_utc, m.Reading.row_hash).limit(limit)
    if station_id is not None:
        stmt = stmt.where(m.Reading.station_id == station_id)
    if parameter is not None:
        stmt = stmt.where(m.Reading.parameter == parameter)
    if start is not None:
        stmt = stmt.where(m.Reading.timestamp_utc >= start)
    if end is not None:
        stmt = stmt.where(m.Reading.timestamp_utc <= end)
    if after is not None:
        after_ts, after_hash = datetime.fromisoformat(after[0]), after[1]
        stmt = stmt.where(
            (m.Reading.timestamp_utc > after_ts)
            | ((m.Reading.timestamp_utc == after_ts) & (m.Reading.row_hash > after_hash))
        )
    return (await session.scalars(stmt)).all()


async def list_defects(
    session: AsyncSession,
    *,
    limit: int,
    after: int | None,
    code: str | None = None,
    station_id: str | None = None,
    severity: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Sequence[m.Defect]:
    stmt = select(m.Defect).order_by(m.Defect.id).limit(limit)
    if code is not None:
        stmt = stmt.where(m.Defect.reason_code == code)
    if station_id is not None:
        stmt = stmt.where(m.Defect.station_id == station_id)
    if severity is not None:
        stmt = stmt.where(m.Defect.severity == severity)
    if start is not None:
        stmt = stmt.where(m.Defect.timestamp_utc >= start)
    if end is not None:
        stmt = stmt.where(m.Defect.timestamp_utc <= end)
    if after is not None:
        stmt = stmt.where(m.Defect.id > after)
    return (await session.scalars(stmt)).all()


async def get_defect(session: AsyncSession, defect_id: int) -> m.Defect | None:
    return await session.get(m.Defect, defect_id)


async def residuals_for_station(
    session: AsyncSession, station_id: str, *, parameter: str | None = None
) -> Sequence[m.Residual]:
    """Stored deweathered residuals for a station (optionally one parameter), time-ordered."""
    stmt = (
        select(m.Residual)
        .where(m.Residual.station_id == station_id)
        .order_by(m.Residual.parameter, m.Residual.timestamp_utc)
    )
    if parameter is not None:
        stmt = stmt.where(m.Residual.parameter == parameter)
    return (await session.scalars(stmt)).all()


def _frame_from_reading_rows(rows: Sequence[m.Reading]) -> pd.DataFrame:
    import pandas as pd

    from provenance.schema import canonical as C

    if not rows:
        return pd.DataFrame(columns=list(C.LONG_COLUMNS))
    frame = pd.DataFrame(
        {
            C.STATION_ID: [r.station_id for r in rows],
            C.PARAMETER: [r.parameter for r in rows],
            C.TIMESTAMP: [pd.Timestamp(r.timestamp_utc) for r in rows],
            C.VALUE: [r.value for r in rows],
            C.UNIT: [r.unit for r in rows],
            C.INSTRUMENT_ID: pd.Series([r.instrument_id for r in rows], dtype="string"),
            C.SOURCE_FILE: [r.source_file for r in rows],
        }
    )
    frame = C.add_row_hash(frame)
    return C.validate(frame)


async def station_frame(session: AsyncSession, station_id: str) -> pd.DataFrame:
    """Reconstruct a station's readings as a canonical long frame.

    Used by the explain layer to rebuild the feature matrix for one station without
    re-reading the source files. Returns an empty (correctly-typed) frame when the
    station has no readings.
    """
    rows = (
        await session.scalars(
            select(m.Reading)
            .where(m.Reading.station_id == station_id)
            .order_by(m.Reading.parameter, m.Reading.timestamp_utc)
        )
    ).all()
    return _frame_from_reading_rows(rows)


async def network_frame(session: AsyncSession) -> pd.DataFrame:
    """Reconstruct every station's readings as one canonical long frame.

    Used by the graph-attention endpoint to rebuild the multi-station feature matrix
    the HST-GAT needs, without re-reading the source files (mirrors
    :func:`station_frame` without the station filter).
    """
    rows = (
        await session.scalars(
            select(m.Reading).order_by(
                m.Reading.station_id, m.Reading.parameter, m.Reading.timestamp_utc
            )
        )
    ).all()
    return _frame_from_reading_rows(rows)


async def list_events(
    session: AsyncSession, *, limit: int, after: int | None, station_id: str | None = None
) -> Sequence[m.Event]:
    stmt = select(m.Event).order_by(m.Event.id).limit(limit)
    if station_id is not None:
        stmt = stmt.where(m.Event.station_id == station_id)
    if after is not None:
        stmt = stmt.where(m.Event.id > after)
    return (await session.scalars(stmt)).all()


async def list_audit_runs(
    session: AsyncSession, *, limit: int, after: str | None
) -> Sequence[m.AuditRun]:
    # Ordered by id for keyset correctness (the cursor filters id > after); the
    # newest run is available separately via latest_audit_run().
    stmt = select(m.AuditRun).order_by(m.AuditRun.id).limit(limit)
    if after is not None:
        stmt = stmt.where(m.AuditRun.id > after)
    return (await session.scalars(stmt)).all()


async def get_audit_run(session: AsyncSession, run_id: str) -> m.AuditRun | None:
    return await session.get(m.AuditRun, run_id)


async def latest_audit_run(session: AsyncSession) -> m.AuditRun | None:
    stmt = select(m.AuditRun).order_by(m.AuditRun.generated_at.desc(), m.AuditRun.id).limit(1)
    return (await session.scalars(stmt)).first()


async def latest_trust_for_station(session: AsyncSession, station_id: str) -> m.TrustScore | None:
    stmt = (
        select(m.TrustScore)
        .where(m.TrustScore.station_id == station_id)
        .order_by(m.TrustScore.timestamp_utc.desc())
        .limit(1)
    )
    return (await session.scalars(stmt)).first()


async def trust_series_for_station(
    session: AsyncSession,
    station_id: str,
    *,
    limit: int,
    after: str | None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Sequence[m.TrustScore]:
    stmt = (
        select(m.TrustScore)
        .where(m.TrustScore.station_id == station_id)
        .order_by(m.TrustScore.timestamp_utc, m.TrustScore.station_id)
        .limit(limit)
    )
    if start is not None:
        stmt = stmt.where(m.TrustScore.timestamp_utc >= start)
    if end is not None:
        stmt = stmt.where(m.TrustScore.timestamp_utc <= end)
    if after is not None:
        stmt = stmt.where(m.TrustScore.timestamp_utc > datetime.fromisoformat(after))
    return (await session.scalars(stmt)).all()


async def defects_for_audit_run(session: AsyncSession, run_id: str) -> Sequence[m.Defect]:
    """Every defect for a run, in a stable order — the audit-trail export source."""
    stmt = (
        select(m.Defect)
        .where(m.Defect.audit_run_id == run_id)
        .order_by(
            m.Defect.station_id,
            m.Defect.parameter,
            m.Defect.timestamp_utc,
            m.Defect.reason_code,
        )
    )
    return (await session.scalars(stmt)).all()


async def coverage_facts_for_audit_run(
    session: AsyncSession, run_id: str
) -> Sequence[m.CoverageFact]:
    stmt = (
        select(m.CoverageFact)
        .where(m.CoverageFact.audit_run_id == run_id)
        .order_by(m.CoverageFact.station_id, m.CoverageFact.parameter)
    )
    return (await session.scalars(stmt)).all()


async def last_reading_at_by_station(session: AsyncSession) -> dict[str, datetime]:
    """The most recent reading timestamp for each station, from the readings table."""
    stmt = select(m.Reading.station_id, func.max(m.Reading.timestamp_utc)).group_by(
        m.Reading.station_id
    )
    rows = (await session.execute(stmt)).all()
    return {str(station): ts for station, ts in rows if ts is not None}


async def quality_summary(session: AsyncSession, run_id: str) -> list[dict[str, Any]]:
    """Per-station Data Quality Monitor payload for a given run."""
    stations = (await session.scalars(select(m.Station).order_by(m.Station.station_id))).all()
    defects = await defects_for_audit_run(session, run_id)
    last_reading = await last_reading_at_by_station(session)
    trust_rows = (
        await session.scalars(select(m.TrustScore).where(m.TrustScore.audit_run_id == run_id))
    ).all()
    latest_trust: dict[str, m.TrustScore] = {}
    for t in trust_rows:
        cur = latest_trust.get(t.station_id)
        if cur is None or t.timestamp_utc > cur.timestamp_utc:
            latest_trust[t.station_id] = t

    flags_by_station: dict[str, int] = {}
    for d in defects:
        if d.counts_toward_rate:
            flags_by_station[d.station_id] = flags_by_station.get(d.station_id, 0) + 1

    out: list[dict[str, Any]] = []
    for s in stations:
        ts = latest_trust.get(s.station_id)
        out.append(
            {
                "station_id": s.station_id,
                "zone_type": s.zone_type,
                "health": None if ts is None else _component_value(ts, "HealthConf"),
                "trust": None if ts is None else ts.trust,
                "flag_count": flags_by_station.get(s.station_id, 0),
                "n_parameters": len(s.coverage),
                "last_reading_at": (
                    last_reading[s.station_id].isoformat() if s.station_id in last_reading else None
                ),
                "components": [] if ts is None else list(ts.components),
                "reason_codes": [] if ts is None else list(ts.reason_codes),
                "evidence": {} if ts is None else _merged_evidence(ts),
            }
        )
    return out


def _merged_evidence(trust: m.TrustScore) -> dict[str, Any]:
    """The components' figures, merged - the map a reason-code sentence renders with."""
    merged: dict[str, Any] = {}
    for c in trust.components:
        merged.update(c.get("evidence") or {})
    return merged


def _component_value(trust: m.TrustScore, name: str) -> float | None:
    for c in trust.components:
        if c.get("name") == name:
            value = c.get("value")
            return None if value is None else float(value)
    return None
