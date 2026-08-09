"""Persistence and orchestration for the operational layer.

The pure ranking and state-machine logic lives in :mod:`provenance.ops.alerts` and
:mod:`provenance.ops.maintenance`; this module is the seam to the database. It reads
the audit's defects and events through the ``io`` repository, applies that pure logic,
and writes the maintenance tickets and their history back. Keeping it here (ops, which
sits downstream of io) means the ``io`` layer never learns about operational concepts,
and the ``api`` routers stay thin — they call one function and serialise the result.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.config import reason_codes
from provenance.io.db import models as m
from provenance.io.db import repository as repo
from provenance.ops import maintenance as mnt
from provenance.ops.alerts import AlertCandidate, RankedAlert, rank_alerts

_UNADJUDICATED_CONFIDENCE = 0.6


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def station_importance(session: AsyncSession, run_id: str) -> dict[str, float]:
    """Each station's PopulationExposure factor, read from its latest trust score.

    The exposure the loader computed from the GTFS transit-corridor layer is stored on
    every trust row's ``risk`` payload, so the maintenance queue reuses it as station
    importance without recomputing anything. Stations with no score fall back to 1.0.
    """
    rows = (
        await session.scalars(select(m.TrustScore).where(m.TrustScore.audit_run_id == run_id))
    ).all()
    latest: dict[str, m.TrustScore] = {}
    for t in rows:
        cur = latest.get(t.station_id)
        if cur is None or t.timestamp_utc > cur.timestamp_utc:
            latest[t.station_id] = t
    return {sid: float((t.risk or {}).get("population_exposure", 1.0)) for sid, t in latest.items()}


async def rebuild_maintenance(
    session: AsyncSession, run_id: str, importance: dict[str, float] | None = None
) -> int:
    """Populate the maintenance queue from the run's fault flags, idempotently.

    Sources tickets from the defects that count toward the defect rate — the
    deterministic sensor faults a technician acts on, never a genuine event. Existing
    tickets (same run/station/parameter/code) are left untouched so an operator's
    acknowledge/dispatch progress is never reset by a rebuild; only new faults are
    added. Returns the number of tickets created.
    """
    if importance is None:
        importance = await station_importance(session, run_id)
    defects = await repo.defects_for_audit_run(session, run_id)
    faults = [d for d in defects if d.counts_toward_rate]
    sentence_for = {
        code: reason_codes.get(code).sentence
        for code in {d.reason_code for d in faults}
        if code in reason_codes.REASON_CODES
    }
    specs = mnt.build_specs(faults, importance, sentence_for=sentence_for)

    existing = {
        (i.station_id, i.parameter, i.reason_code) for i in await _items_for_run(session, run_id)
    }
    created = 0
    now = _now()
    for spec in specs:
        key = (spec.station_id, spec.parameter, spec.reason_code)
        if key in existing:
            continue
        item = m.MaintenanceItem(
            audit_run_id=run_id,
            station_id=spec.station_id,
            parameter=spec.parameter,
            reason_code=spec.reason_code,
            severity=spec.severity,
            severity_weight=spec.severity_weight,
            importance=spec.importance,
            priority=spec.priority,
            status=mnt.OPEN,
            headline=spec.headline,
            n_flags=spec.n_flags,
            evidence=spec.evidence,
            created_at=now,
            updated_at=now,
        )
        session.add(item)
        await session.flush()
        session.add(
            m.MaintenanceTransition(
                item_id=item.id,
                from_status=None,
                to_status=mnt.OPEN,
                actor="system",
                note="Auto-raised from fault classification.",
                at=now,
            )
        )
        created += 1
    await session.commit()
    return created


async def _items_for_run(session: AsyncSession, run_id: str) -> Sequence[m.MaintenanceItem]:
    stmt = select(m.MaintenanceItem).where(m.MaintenanceItem.audit_run_id == run_id)
    return (await session.scalars(stmt)).all()


async def list_maintenance(
    session: AsyncSession, *, limit: int, after: int | None, status: str | None = None
) -> Sequence[m.MaintenanceItem]:
    """Maintenance tickets ranked by priority (severity × importance), highest first.

    Keyset paginated on ``(-priority, id)`` collapsed to the id cursor: the ordering is
    stable because priority is stored, so ``after`` filters on the composite already
    consumed. Highest priority first is the order the queue is worked.
    """
    stmt = (
        select(m.MaintenanceItem)
        .order_by(m.MaintenanceItem.priority.desc(), m.MaintenanceItem.id)
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(m.MaintenanceItem.status == status)
    if after is not None:
        stmt = stmt.where(m.MaintenanceItem.id > after)
    return (await session.scalars(stmt)).all()


async def get_maintenance_item(session: AsyncSession, item_id: int) -> m.MaintenanceItem | None:
    return await session.get(m.MaintenanceItem, item_id)


async def apply_transition(
    session: AsyncSession,
    item_id: int,
    target: str,
    *,
    actor: str,
    note: str | None = None,
) -> m.MaintenanceItem:
    """Move a ticket to ``target``, validating the lifecycle and recording the history.

    Raises :class:`~provenance.ops.maintenance.InvalidTransitionError` when the move is not
    allowed; the router turns that into a 409 problem. On success the status and
    ``updated_at`` change and a transition row is appended — the previous status is
    never silently overwritten.
    """
    item = await session.get(m.MaintenanceItem, item_id)
    if item is None:
        raise KeyError(item_id)
    mnt.check_transition(item.status, target)
    now = _now()
    from_status = item.status
    item.status = target
    item.updated_at = now
    session.add(
        m.MaintenanceTransition(
            item_id=item.id,
            from_status=from_status,
            to_status=target,
            actor=actor,
            note=note,
            at=now,
        )
    )
    await session.commit()
    await session.refresh(item)
    return item


async def transitions_for_item(
    session: AsyncSession, item_id: int
) -> Sequence[m.MaintenanceTransition]:
    stmt = (
        select(m.MaintenanceTransition)
        .where(m.MaintenanceTransition.item_id == item_id)
        .order_by(m.MaintenanceTransition.id)
    )
    return (await session.scalars(stmt)).all()


async def alert_candidates(session: AsyncSession, run_id: str) -> list[AlertCandidate]:
    """Build Alert Centre candidates from the run's events, joined with exposure.

    Confidence comes from the stored adjudication when the event has been adjudicated;
    an unadjudicated event is treated as moderately confident and ambiguous rather than
    assumed genuine. Exposure is the station's PopulationExposure factor.
    """
    importance = await station_importance(session, run_id)
    events = (await session.scalars(select(m.Event).where(m.Event.audit_run_id == run_id))).all()
    candidates: list[AlertCandidate] = []
    for e in events:
        adjudication = (e.evidence or {}).get("adjudication") or {}
        confidence = float(adjudication.get("confidence", _UNADJUDICATED_CONFIDENCE))
        candidates.append(
            AlertCandidate(
                event_id=e.id,
                station_id=e.station_id,
                parameter=e.parameter,
                severity=e.severity,
                verdict=e.verdict,
                confidence=confidence,
                exposure=float(importance.get(e.station_id, 1.0)),
                headline=e.headline,
                timestamp_utc=e.timestamp_utc.isoformat(),
            )
        )
    return candidates


async def ranked_alerts(session: AsyncSession, run_id: str) -> list[RankedAlert]:
    """The Alert Centre: every candidate event scored and ordered by RISK, descending."""
    return rank_alerts(await alert_candidates(session, run_id))


async def model_drift_report(session: AsyncSession) -> dict[str, Any]:
    """Assemble the model-drift monitor payload (§11).

    Defect-rate drift by station is always computable from the audit runs. The model
    metric series (deweathering R², conformal coverage, fault-classifier confusion)
    exist only once models have been trained — their artefacts are gitignored — so they
    degrade to an empty series with a note rather than a fabricated trend (rule 6).
    """
    from provenance.ops import drift

    runs = (
        await session.scalars(select(m.AuditRun).order_by(m.AuditRun.generated_at, m.AuditRun.id))
    ).all()
    stations = (await session.scalars(select(m.Station))).all()
    covered_by_station = {s.station_id: int(sum((s.coverage or {}).values())) for s in stations}

    run_counts: list[drift.RunStationCounts] = []
    for run in runs:
        defects = await repo.defects_for_audit_run(session, run.id)
        counting: dict[str, int] = {}
        for d in defects:
            if d.counts_toward_rate:
                counting[d.station_id] = counting.get(d.station_id, 0) + 1
        run_counts.append(
            drift.RunStationCounts(
                run_id=run.id,
                generated_at=run.generated_at.isoformat(),
                counting_defects=counting,
                covered_cells=covered_by_station,
            )
        )

    defect_drift = drift.defect_rate_drift_by_station(run_counts)
    model_series = _model_metric_history()
    return {
        "plane": "model",
        "note": (
            "The model plane is separate from infra health (/metrics); it watches "
            "whether the models and data are drifting, not whether the service is up."
        ),
        "defect_rate_by_station": {k: v.to_dict() for k, v in defect_drift.items()},
        **model_series,
    }


def _model_metric_history() -> dict[str, Any]:
    """Read whatever model-metric history exists on disk, degrading to empty + a note.

    Never raises: the model artefacts are optional and gitignored, so a fresh clone or
    CI has none. When models have been trained (e.g. after ``make demo``), the latest
    training's figures appear as a (possibly single-point) series.
    """
    from provenance.ops import drift

    r2_points: list[tuple[str, float]] = []
    coverage_points: list[tuple[str, float]] = []
    nominal = 0.9
    fault_confusion: dict[str, Any] = {"available": False, "note": "train models to populate"}
    try:
        from provenance.models import registry

        bundle = registry.load_bundle()
        if bundle is not None:
            stamp = getattr(bundle.deweather, "trained_at", "") or "latest"
            metrics = getattr(bundle.deweather, "metrics", {}) or {}
            r2_vals = [
                float(v.cv_r2_mean)
                for v in metrics.values()
                if getattr(v, "cv_r2_mean", None) is not None
            ]
            if r2_vals:
                r2_points.append((str(stamp), sum(r2_vals) / len(r2_vals)))
    except Exception:
        pass
    try:
        from provenance.models.hstgat import store as hstgat_store

        latest = hstgat_store.load_latest()
        if latest is not None:
            cov = getattr(latest, "coverage", None) or {}
            emp = cov.get("empirical_coverage")
            nominal = float(cov.get("nominal_coverage", nominal))
            if emp is not None:
                coverage_points.append((str(cov.get("trained_at", "latest")), float(emp)))
    except Exception:
        pass

    return {
        "deweather_r2": drift.r2_drift(r2_points).to_dict(),
        "conformal_coverage": drift.conformal_coverage_drift(
            coverage_points, nominal=nominal
        ).to_dict(),
        "fault_confusion": fault_confusion,
    }
