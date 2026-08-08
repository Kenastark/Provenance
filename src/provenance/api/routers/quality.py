"""Quality summary — the Data Quality Monitor payload.

One row per station for a given audit run (the latest by default): its health
component, current trust, and how many defect-counting flags fired. This is the
at-a-glance operator view; the detail lives behind the other endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.api.schemas import QualityStationOut, QualitySummaryOut
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/quality", tags=["quality"])


@router.get("/summary", response_model=QualitySummaryOut)
async def quality_summary(
    run_id: str | None = Query(default=None, description="Audit run; defaults to the latest."),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> QualitySummaryOut:
    if run_id is None:
        latest = await repo.latest_audit_run(session)
        if latest is None:
            raise ProblemException(404, "No audit run exists yet. Load a data drop first.")
        run_id = latest.id
    elif await repo.get_audit_run(session, run_id) is None:
        raise ProblemException(404, f"No audit run with id {run_id!r}.")

    rows = await repo.quality_summary(session, run_id)
    return QualitySummaryOut(
        audit_run_id=run_id,
        stations=[QualityStationOut(**r) for r in rows],
    )
