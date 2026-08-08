"""Audit-run endpoints. Researcher access: the runs and one run's full summary."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.api.pagination import Page, clamp_limit, decode_cursor, encode_cursor
from provenance.api.schemas import AuditRunOut
from provenance.io.db import models as m
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/audit", tags=["audit"])


def _to_out(r: m.AuditRun) -> AuditRunOut:
    return AuditRunOut(
        id=r.id,
        code_version=r.code_version,
        config_hash=r.config_hash,
        data_checksum=r.data_checksum,
        generated_at=r.generated_at.isoformat(),
        n_rows=r.n_rows,
        n_defective_cells=r.n_defective_cells,
        n_covered_cells=r.n_covered_cells,
        defect_rate=r.defect_rate,
        conventional_completeness_pct=r.conventional_completeness_pct,
        ingest_batch_id=r.ingest_batch_id,
    )


@router.get("/runs", response_model=Page[AuditRunOut])
async def list_runs(
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.RESEARCHER)),
) -> Page[AuditRunOut]:
    n = clamp_limit(limit)
    after = decode_cursor(cursor)
    rows = await repo.list_audit_runs(session, limit=n + 1, after=str(after) if after else None)
    items = [_to_out(r) for r in rows[:n]]
    next_cursor = encode_cursor(rows[n - 1].id) if len(rows) > n else None
    return Page(items=items, next_cursor=next_cursor, count=len(items))


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.RESEARCHER)),
) -> dict[str, Any]:
    run = await repo.get_audit_run(session, run_id)
    if run is None:
        raise ProblemException(404, f"No audit run with id {run_id!r}.")
    # The full AuditResult summary is stored verbatim so a run reconstructs without
    # a re-audit; it is returned as-is alongside the flat run header.
    return {"run": _to_out(run).model_dump(), "summary": run.summary}
