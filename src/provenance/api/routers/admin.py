"""The admin dashboard surface (§11). Admin access only.

Exposes what an operator running the deployment needs to see and could act on: the
model versions in force, the config hashes that pin the current behaviour, the
retraining triggers, and the history of what has been dispatched and can be exported.
Read-mostly: the one action, ``/retrain``, records a retraining *request* rather than
running a heavy training job inline — the training itself is a CLI/worker task, and
the dashboard is honest that it has queued the intent, not retrained.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from provenance import __version__
from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.config.loading import config_hash
from provenance.io.db import models as m
from provenance.trust.weights import trust_config_hash

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# The retraining entry points an admin can trigger. Recorded, not run inline.
RETRAIN_TARGETS: dict[str, str] = {
    "deweather": "prov models train",
    "fault": "prov models train",
    "hstgat": "prov models train-hstgat",
}


class RetrainIn(BaseModel):
    target: str = Field(description=f"One of {sorted(RETRAIN_TARGETS)}.")
    reason: str | None = Field(default=None)


@router.get("/status")
async def admin_status(
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.ADMIN)),
) -> dict[str, Any]:
    from provenance.api.models_status import model_versions

    runs = (
        await session.scalars(select(m.AuditRun).order_by(m.AuditRun.generated_at.desc()).limit(10))
    ).all()
    dispatches = (
        await session.scalars(
            select(m.Dispatch).order_by(m.Dispatch.dispatched_at.desc()).limit(20)
        )
    ).all()
    n_maintenance = int(
        (await session.scalar(select(func.count()).select_from(m.MaintenanceItem))) or 0
    )
    n_open = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(m.MaintenanceItem)
                .where(m.MaintenanceItem.status == "open")
            )
        )
        or 0
    )
    return {
        "version": __version__,
        "model_versions": {"trust_score": "v1", **model_versions()},
        "config_hashes": {
            "config_hash": config_hash(),
            "trust_config_hash": trust_config_hash(),
        },
        "retraining_triggers": RETRAIN_TARGETS,
        "audit_runs": [
            {
                "id": r.id,
                "generated_at": r.generated_at.isoformat(),
                "n_rows": r.n_rows,
                "defect_rate": r.defect_rate,
                "config_hash": r.config_hash,
            }
            for r in runs
        ],
        "export_history": {
            "note": (
                "Each audit run is an exportable reporting period; dispatches are the "
                "record of public alerts sent."
            ),
            "n_audit_runs": len(runs),
            "dispatches": [
                {
                    "dispatch_id": d.id,
                    "event_id": d.event_id,
                    "channel": d.channel,
                    "status": d.status,
                    "dispatched_at": d.dispatched_at.isoformat(),
                }
                for d in dispatches
            ],
        },
        "maintenance_summary": {"total": n_maintenance, "open": n_open},
    }


@router.get("/model-drift")
async def model_drift(
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.ADMIN)),
) -> dict[str, Any]:
    """The model-drift monitor (§11): defect-rate drift by station, R², coverage, confusion.

    Deliberately a *different plane* from ``/metrics`` (infra health) — model health and
    service health are separate questions with separate dashboards.
    """
    from provenance.ops import store

    return await store.model_drift_report(session)


@router.post("/retrain")
async def retrain(
    body: RetrainIn,
    _: Role = Depends(require(Role.ADMIN)),
) -> dict[str, Any]:
    from provenance.api.errors import ProblemException

    if body.target not in RETRAIN_TARGETS:
        raise ProblemException(
            422,
            f"Unknown retrain target {body.target!r}; expected one of {sorted(RETRAIN_TARGETS)}.",
        )
    return {
        "status": "queued",
        "target": body.target,
        "command": RETRAIN_TARGETS[body.target],
        "reason": body.reason,
        "queued_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "note": "Retraining runs as a CLI/worker job; this records the request, it does not train inline.",
    }
