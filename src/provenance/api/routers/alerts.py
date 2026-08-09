"""The Alert Centre (§9.5). Operator access.

Candidate events are scored by RISK — consequence-weighted, not certainty-weighted —
and returned in descending risk order, so a high-exposure genuine event sits above a
confident low-exposure sensor fault. Each alert carries the factors behind its risk,
never a bare number.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.io.db import repository as repo
from provenance.ops import store

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    run_id: str | None = Query(default=None, description="Audit run; defaults to the latest."),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.OPERATOR)),
) -> dict[str, Any]:
    if run_id is not None:
        if await repo.get_audit_run(session, run_id) is None:
            raise ProblemException(404, f"No audit run with id {run_id!r}.")
    else:
        latest = await repo.latest_audit_run(session)
        if latest is None:
            return {"audit_run_id": None, "ranked_by": "risk", "items": [], "count": 0}
        run_id = latest.id
    ranked = await store.ranked_alerts(session, run_id)
    items = [a.to_dict() for a in ranked[:limit]]
    return {
        "audit_run_id": run_id,
        "ranked_by": "risk",
        "note": (
            "Ranked by consequence-weighted risk (genuineness × exposure × hazard × "
            "confidence), so a genuine high-exposure event outranks a confident "
            "low-exposure sensor fault."
        ),
        "items": items,
        "count": len(items),
    }
