"""The regulator-facing audit-trail export (§2). Researcher access.

For one reporting period (an audit run) it emits, deterministically, the reading
accounting, the itemised defects and structural exclusions, the model versions, the
sign-off records for any public alerts, and a verification hash — rendered as JSON, a
CSV ledger, or a printable PDF summary. All three come from one
:class:`~provenance.report.regulatory.RegulatoryExport`, so a figure never disagrees
between formats, and the CSV/JSON/hash are byte-for-byte reproducible for a fixed run.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.grid.defect_rate import DEFINITION
from provenance.io.db import models as m
from provenance.io.db import repository as repo
from provenance.report.regulatory import RegulatoryExport

router = APIRouter(prefix="/v1/export", tags=["export"])


async def _resolve_run(session: AsyncSession, run_id: str | None) -> m.AuditRun:
    if run_id is None:
        latest = await repo.latest_audit_run(session)
        if latest is None:
            raise ProblemException(404, "No audit run exists yet. Load a data drop first.")
        return latest
    run = await repo.get_audit_run(session, run_id)
    if run is None:
        raise ProblemException(404, f"No audit run with id {run_id!r}.")
    return run


async def _build_export(session: AsyncSession, run: m.AuditRun) -> RegulatoryExport:
    defects = await repo.defects_for_audit_run(session, run.id)
    coverage_facts = await repo.coverage_facts_for_audit_run(session, run.id)

    # Readings in the period: those loaded by the run's ingest batch (the run and the
    # batch share the data checksum), so the accounting reconciles against the table.
    n_readings = 0
    if run.ingest_batch_id is not None:
        n_readings = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(m.Reading)
                    .where(m.Reading.ingest_batch_id == run.ingest_batch_id)
                )
            )
            or 0
        )

    event_ids = list(
        (await session.scalars(select(m.Event.id).where(m.Event.audit_run_id == run.id))).all()
    )
    signoffs, dispatches = await _signoffs_and_dispatches(session, event_ids)

    from provenance.api.models_status import model_versions

    return RegulatoryExport(
        run={
            "id": run.id,
            "code_version": run.code_version,
            "config_hash": run.config_hash,
            "data_checksum": run.data_checksum,
            "generated_at": run.generated_at.isoformat(),
            "n_rows": run.n_rows,
        },
        definition=DEFINITION,
        accounting={
            "n_readings": n_readings,
            "n_covered_cells": run.n_covered_cells,
            "n_defective_cells": run.n_defective_cells,
            "n_structural_exclusions": len(coverage_facts),
            "defect_rate": run.defect_rate,
            "conventional_completeness_pct": run.conventional_completeness_pct,
        },
        defects=[
            {
                "station_id": d.station_id,
                "parameter": d.parameter,
                "timestamp_utc": d.timestamp_utc.isoformat(),
                "reason_code": d.reason_code,
                "severity": d.severity,
                "counts_toward_rate": d.counts_toward_rate,
                "evidence": dict(d.evidence or {}),
            }
            for d in defects
        ],
        structural_exclusions=[
            {
                "station_id": c.station_id,
                "parameter": c.parameter,
                "domain": c.domain,
                "reason_code": c.reason_code,
                "excluded_cells": c.excluded_cells,
            }
            for c in coverage_facts
        ],
        model_versions={"trust_score": "v1", **model_versions()},
        signoffs=signoffs,
        dispatches=dispatches,
    )


async def _signoffs_and_dispatches(
    session: AsyncSession, event_ids: list[int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not event_ids:
        return [], []
    so_rows = (
        await session.scalars(
            select(m.SignoffToken)
            .where(m.SignoffToken.event_id.in_(event_ids))
            .order_by(m.SignoffToken.created_at, m.SignoffToken.id)
        )
    ).all()
    dp_rows = (
        await session.scalars(
            select(m.Dispatch)
            .where(m.Dispatch.event_id.in_(event_ids))
            .order_by(m.Dispatch.dispatched_at, m.Dispatch.id)
        )
    ).all()
    signoffs = [
        {
            "signoff_id": s.id,
            "event_id": s.event_id,
            "channel": s.channel,
            "operator": s.operator,
            "evidence_hash": s.evidence_hash,
            "model_version": s.model_version,
            "created_at": s.created_at.isoformat(),
            "expires_at": s.expires_at.isoformat(),
        }
        for s in so_rows
    ]
    dispatches = [
        {
            "dispatch_id": d.id,
            "event_id": d.event_id,
            "channel": d.channel,
            "signoff_id": d.signoff_id,
            "status": d.status,
            "dispatched_at": d.dispatched_at.isoformat(),
        }
        for d in dp_rows
    ]
    return signoffs, dispatches


@router.get("/audit-trail")
async def audit_trail(
    run_id: str | None = Query(default=None, description="Audit run; defaults to the latest."),
    fmt: str = Query(default="json", pattern="^(json|csv|pdf)$", alias="format"),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.RESEARCHER)),
) -> Response:
    run = await _resolve_run(session, run_id)
    export = await _build_export(session, run)
    headers = {
        "X-Audit-Run-Id": run.id,
        "X-Defect-Row-Count": str(len(export.defects)),
        "X-Verification-Hash": export.verification_hash(),
    }

    if fmt == "csv":
        return Response(
            content=export.to_csv(),
            media_type="text/csv",
            headers={
                **headers,
                "Content-Disposition": f'attachment; filename="audit-trail-{run.id}.csv"',
            },
        )
    if fmt == "pdf":
        return Response(
            content=export.to_pdf(),
            media_type="application/pdf",
            headers={
                **headers,
                "Content-Disposition": f'attachment; filename="audit-trail-{run.id}.pdf"',
            },
        )
    return JSONResponse(content=export.to_json_dict(), headers=headers)
