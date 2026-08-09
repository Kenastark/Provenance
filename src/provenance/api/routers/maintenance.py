"""The maintenance queue (§9.5). Operator access.

Tickets are auto-raised from fault classifications and ranked by priority (severity ×
station importance). The queue supports the ``acknowledge → dispatch → resolve``
lifecycle, and every move is recorded — the transition history travels with the item.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.api.pagination import Page, clamp_limit, decode_cursor, encode_cursor
from provenance.io.db import models as m
from provenance.io.db import repository as repo
from provenance.ops import store
from provenance.ops.maintenance import InvalidTransitionError

router = APIRouter(prefix="/v1/maintenance", tags=["maintenance"])


class TransitionIn(BaseModel):
    to: str = Field(description="Target status: acknowledged | dispatched | resolved.")
    actor: str = Field(default="operator", description="Who is making the change.")
    note: str | None = Field(default=None)


class RebuildIn(BaseModel):
    run_id: str | None = Field(default=None, description="Audit run; defaults to the latest.")


def _item_dict(
    item: m.MaintenanceItem, *, history: list[m.MaintenanceTransition] | None = None
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": item.id,
        "audit_run_id": item.audit_run_id,
        "station_id": item.station_id,
        "parameter": item.parameter,
        "reason_code": item.reason_code,
        "severity": item.severity,
        "severity_weight": item.severity_weight,
        "importance": item.importance,
        "priority": item.priority,
        "status": item.status,
        "headline": item.headline,
        "n_flags": item.n_flags,
        "evidence": dict(item.evidence or {}),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
    if history is not None:
        out["history"] = [
            {
                "from_status": t.from_status,
                "to_status": t.to_status,
                "actor": t.actor,
                "note": t.note,
                "at": t.at.isoformat(),
            }
            for t in history
        ]
    return out


async def _resolve_run_id(session: AsyncSession, run_id: str | None) -> str:
    if run_id is not None:
        if await repo.get_audit_run(session, run_id) is None:
            raise ProblemException(404, f"No audit run with id {run_id!r}.")
        return run_id
    latest = await repo.latest_audit_run(session)
    if latest is None:
        raise ProblemException(404, "No audit run exists yet. Load a data drop first.")
    return latest.id


@router.get("", response_model=Page[dict[str, Any]])
async def list_maintenance(
    status: str | None = Query(default=None, description="Filter by lifecycle status."),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.OPERATOR)),
) -> Page[dict[str, Any]]:
    n = clamp_limit(limit)
    after = decode_cursor(cursor)
    rows = await store.list_maintenance(
        session, limit=n + 1, after=int(after) if after is not None else None, status=status
    )
    items = [_item_dict(i) for i in rows[:n]]
    next_cursor = encode_cursor(rows[n - 1].id) if len(rows) > n else None
    return Page(items=items, next_cursor=next_cursor, count=len(items))


@router.post("/rebuild")
async def rebuild(
    body: RebuildIn | None = None,
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.OPERATOR)),
) -> dict[str, Any]:
    run_id = await _resolve_run_id(session, (body or RebuildIn()).run_id)
    created = await store.rebuild_maintenance(session, run_id)
    return {"audit_run_id": run_id, "created": created}


@router.get("/{item_id}")
async def get_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.OPERATOR)),
) -> dict[str, Any]:
    item = await store.get_maintenance_item(session, item_id)
    if item is None:
        raise ProblemException(404, f"No maintenance item {item_id}.")
    # Fetch the history explicitly rather than touching the lazy relationship, which an
    # async session cannot load on attribute access.
    history = list(await store.transitions_for_item(session, item_id))
    return _item_dict(item, history=history)


@router.post("/{item_id}/transition")
async def transition(
    item_id: int,
    body: TransitionIn,
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.OPERATOR)),
) -> dict[str, Any]:
    try:
        item = await store.apply_transition(
            session, item_id, body.to, actor=body.actor, note=body.note
        )
    except KeyError as exc:
        raise ProblemException(404, f"No maintenance item {item_id}.") from exc
    except InvalidTransitionError as exc:
        raise ProblemException(
            409,
            str(exc),
            type_="https://provenance.example/problems/invalid-transition",
        ) from exc
    history = list(await store.transitions_for_item(session, item_id))
    return _item_dict(item, history=history)
