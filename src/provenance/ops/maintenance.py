"""The maintenance queue: fault classifications → prioritised, trackable tickets (§9.5).

A ticket is raised for each distinct fault a station carries — the deterministic
sensor problems the audit flags (frozen sensors, detection-limit floors, physical
impossibilities, duplicate timestamps): the ones that need a technician, not a public
alert. Genuine events do not belong here; they go to the Alert Centre.

Priority is ``severity_weight × station_importance``, and importance is the station's
PopulationExposure (from the GTFS transit-corridor layer), so a frozen sensor on a
busy transit corridor is dispatched before the same fault at a rural background site.

The lifecycle is a small explicit state machine — ``open → acknowledged → dispatched
→ resolved`` — and every move is appended to the item's history, so the queue is
auditable rather than a status that silently overwrites itself.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from provenance.ops.severity import severity_weight

OPEN = "open"
ACKNOWLEDGED = "acknowledged"
DISPATCHED = "dispatched"
RESOLVED = "resolved"

STATUSES: tuple[str, ...] = (OPEN, ACKNOWLEDGED, DISPATCHED, RESOLVED)

# Forward-only lifecycle. A resolved ticket is terminal; an item may be resolved
# straight from acknowledged (a false alarm the operator clears without a dispatch).
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    OPEN: frozenset({ACKNOWLEDGED}),
    ACKNOWLEDGED: frozenset({DISPATCHED, RESOLVED}),
    DISPATCHED: frozenset({RESOLVED}),
    RESOLVED: frozenset(),
}


class InvalidTransitionError(Exception):
    """Raised when a caller asks for a lifecycle move the state machine forbids."""


def can_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, frozenset())


def check_transition(current: str, target: str) -> None:
    if target not in STATUSES:
        raise InvalidTransitionError(f"{target!r} is not a maintenance status.")
    if not can_transition(current, target):
        allowed = sorted(VALID_TRANSITIONS.get(current, frozenset()))
        raise InvalidTransitionError(
            f"Cannot move a maintenance item from {current!r} to {target!r} "
            f"(allowed from {current!r}: {allowed or 'none — terminal'})."
        )


def priority(severity: str, importance: float) -> float:
    """severity_weight × station importance. Higher is more urgent."""
    return round(severity_weight(severity) * float(importance), 6)


class _FaultRow(Protocol):
    station_id: str
    parameter: str
    reason_code: str
    severity: str


@dataclass(frozen=True, slots=True)
class MaintenanceSpec:
    """A ticket to raise, before it is persisted with a status and history."""

    station_id: str
    parameter: str
    reason_code: str
    severity: str
    severity_weight: float
    importance: float
    priority: float
    headline: str
    n_flags: int
    evidence: dict[str, Any] = field(default_factory=dict)


def build_specs(
    faults: Sequence[_FaultRow],
    importance: dict[str, float],
    *,
    sentence_for: dict[str, str] | None = None,
) -> list[MaintenanceSpec]:
    """Group fault rows into one prioritised ticket per (station, parameter, code).

    ``importance`` maps station id → PopulationExposure factor (default 1.0 for a
    station with no computed exposure). ``sentence_for`` optionally maps a reason code
    to its operator-facing sentence for the headline. The result is sorted by priority
    descending with a deterministic tiebreak, so the queue is byte-stable.
    """
    sentence_for = sentence_for or {}
    groups: dict[tuple[str, str, str], list[_FaultRow]] = {}
    for f in faults:
        groups.setdefault((f.station_id, f.parameter, f.reason_code), []).append(f)

    specs: list[MaintenanceSpec] = []
    for (station_id, parameter, reason_code), rows in groups.items():
        # The worst severity present drives the ticket.
        severities = Counter(r.severity for r in rows)
        worst = max(severities, key=lambda s: severity_weight(s))
        imp = float(importance.get(station_id, 1.0))
        sw = severity_weight(worst)
        sentence = sentence_for.get(reason_code, reason_code)
        specs.append(
            MaintenanceSpec(
                station_id=station_id,
                parameter=parameter,
                reason_code=reason_code,
                severity=worst,
                severity_weight=sw,
                importance=imp,
                priority=round(sw * imp, 6),
                headline=f"{station_id} · {parameter} · {sentence}",
                n_flags=len(rows),
                evidence={
                    "n_flags": len(rows),
                    "severity_mix": dict(sorted(severities.items())),
                    "importance": round(imp, 6),
                },
            )
        )
    specs.sort(key=lambda s: (-s.priority, s.station_id, s.parameter, s.reason_code))
    return specs
