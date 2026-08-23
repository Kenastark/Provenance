"""Write adjudication verdicts back onto the stored events.

The audit persists candidate events with ``verdict = NULL`` (the io/db layer cannot
import the graph, so it cannot adjudicate). This is the graph-layer step that fills
them in: it adjudicates each stored event over the wind graph and writes the verdict
plus the full evidence bundle back onto ``Event.verdict`` and ``Event.evidence
["adjudication"]``. The API's existing ``EventOut`` then serves both with no contract
change — the ``verdict`` field was reserved for exactly this since phase 2.

**Not every stored event has a plume question to answer.** The adjudicator asks one
thing: *did the wind carry this rise to the neighbours downwind?* An event with no
reading at its own timestamp — a communication outage, say — has no rise to carry, so
there is nothing to corroborate and no verdict to reach. Those events keep
``verdict = NULL``, and this module records **why** under
``Event.evidence["adjudication_not_applicable"]`` so the two very different meanings of
a null verdict stay distinguishable downstream:

* no record  → not adjudicated yet (``prov graph adjudicate-db`` has not run);
* a record   → adjudicated over, and the plume test does not apply.

Without that distinction the dashboard shows "pending adjudication" forever on events
that were in fact considered and settled, which reads as a bug and is, worse, untrue.
The reason is *derived* from the frame (is the parameter carried? is there a reading at
that hour?), never from a hardcoded list of reason codes — standing rules 1 and 2.

An outage is deliberately **not** folded into ``AMBIGUOUS``. AMBIGUOUS means *we are
unsure, route this to a human* (§7.5); we are not unsure about an outage, we know
exactly what it is. Overloading it would erode the one signal that makes AMBIGUOUS
worth having.

Graph → io/db is a legal dependency (io is upstream); the reverse would not be, which
is why this lives here and not in the loader.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from provenance.schema import canonical as C

NOT_APPLICABLE_KEY = "adjudication_not_applicable"
"""Where the skip record lives on ``Event.evidence``. Read by the API and the dashboard."""


@dataclass(frozen=True, slots=True)
class SweepResult:
    """What one pass over the stored events did.

    ``not_applicable`` is reported separately rather than silently folded into the
    adjudicated count: "we judged 19" and "we judged 19 and the other 5 had no plume
    question" are different statements, and the operator is owed the second one.
    """

    adjudicated: int
    not_applicable: int

    @property
    def total(self) -> int:
        return self.adjudicated + self.not_applicable


async def adjudicate_stored_events(
    session: AsyncSession,
    frame: pd.DataFrame,
    station_meta: dict[str, Any],
    *,
    cfg: dict[str, Any] | None = None,
    audit_run_id: str | None = None,
) -> SweepResult:
    """Adjudicate every stored event and persist its verdict + evidence.

    Idempotent: re-running re-adjudicates and overwrites, which is safe because the
    verdict is a pure function of the frame, the geometry, the wind, and the config.
    Events with no plume question to answer keep a null verdict and gain a recorded
    reason instead (see the module docstring).
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
    skipped = 0
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
        evidence = dict(event.evidence or {})
        if candidate is None:
            event.verdict = None
            evidence.pop("adjudication", None)  # a stale bundle from an earlier drop
            evidence[NOT_APPLICABLE_KEY] = _not_applicable_record(
                frame, event.station_id, event.parameter, pd.Timestamp(event.timestamp_utc)
            )
            event.evidence = evidence
            skipped += 1
            continue
        adjudication = validate_event(candidate, points, wind, frame, cfg)
        event.verdict = adjudication.verdict.value
        evidence.pop(NOT_APPLICABLE_KEY, None)  # it applies now; clear any stale record
        evidence["adjudication"] = adjudication.to_dict()
        event.evidence = evidence  # reassign so the JSON column registers the change
        updated += 1

    await session.commit()
    return SweepResult(adjudicated=updated, not_applicable=skipped)


def _not_applicable_record(
    frame: pd.DataFrame, station_id: str, parameter: str, timestamp: pd.Timestamp
) -> dict[str, str]:
    """Why the plume test does not apply to this event, derived from the frame.

    Mirrors ``replay.build_candidate``'s own two ``None`` paths so the recorded reason
    is the real one rather than a guess. Never keyed off a reason code: what matters is
    whether there is a rise to propagate, and that is a property of the data.
    """
    carried = frame[(frame[C.STATION_ID] == station_id) & (frame[C.PARAMETER] == parameter)]
    if carried.empty:
        return {
            "basis": "parameter_not_carried",
            "reason": (
                f"{station_id} carries no {parameter} readings in this drop, so there is "
                "no series to propagate and no downwind comparison to make."
            ),
        }
    return {
        "basis": "no_reading_at_event_time",
        "reason": (
            f"There is no {parameter} reading at {station_id} for "
            f"{pd.Timestamp(timestamp).isoformat()}, so there is no rise for the wind to "
            "carry and nothing for the downwind neighbours to corroborate. The plume test "
            "does not apply; this is not an unsettled call."
        ),
    }


def _evidence_value(evidence: dict[str, Any] | None) -> float | None:
    if not evidence:
        return None
    value = evidence.get("value")
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
