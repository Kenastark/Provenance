"""Write adjudication verdicts back onto the stored events.

The audit persists candidate events with ``verdict = NULL`` (the io/db layer cannot
import the graph, so it cannot adjudicate). This is the graph-layer step that fills
them in: it adjudicates each stored event over the wind graph and writes the verdict
plus the full evidence bundle back onto ``Event.verdict`` and ``Event.evidence
["adjudication"]``. The API's existing ``EventOut`` then serves both with no contract
change — the ``verdict`` field was reserved for exactly this since phase 2.

Graph → io/db is a legal dependency (io is upstream); the reverse would not be, which
is why this lives here and not in the loader.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.config.loading import load_graph_config
from provenance.graph.adjudicate import AdjudicatorParams, validate_event
from provenance.graph.build import station_points_from_metadata
from provenance.graph.replay import build_candidate
from provenance.graph.wind import WindField
from provenance.io.db import models as m


async def adjudicate_stored_events(
    session: AsyncSession,
    frame: pd.DataFrame,
    station_meta: dict[str, Any],
    *,
    cfg: dict[str, Any] | None = None,
    audit_run_id: str | None = None,
) -> int:
    """Adjudicate every stored event and persist its verdict + evidence. Returns the count.

    Idempotent: re-running re-adjudicates and overwrites, which is safe because the
    verdict is a pure function of the frame, the geometry, the wind, and the config.
    """
    cfg = cfg or load_graph_config()
    params = AdjudicatorParams.from_config(cfg)
    points = station_points_from_metadata(station_meta)
    wind = WindField.from_frame(frame)

    stmt = select(m.Event).order_by(m.Event.id)
    if audit_run_id is not None:
        stmt = stmt.where(m.Event.audit_run_id == audit_run_id)
    events = (await session.scalars(stmt)).all()

    updated = 0
    for event in events:
        candidate = build_candidate(
            frame,
            event.station_id,
            event.parameter,
            pd.Timestamp(event.timestamp_utc),
            window_hours=params.baseline_window_hours,
            anomaly_score=float(event.rank),
            fallback_value=_evidence_value(event.evidence),
        )
        if candidate is None:
            continue
        adjudication = validate_event(candidate, points, wind, frame, cfg)
        event.verdict = adjudication.verdict.value
        evidence = dict(event.evidence or {})
        evidence["adjudication"] = adjudication.to_dict()
        event.evidence = evidence  # reassign so the JSON column registers the change
        updated += 1

    await session.commit()
    return updated


def _evidence_value(evidence: dict[str, Any] | None) -> float | None:
    if not evidence:
        return None
    value = evidence.get("value")
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
