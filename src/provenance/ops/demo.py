"""Deterministic demo replay (§ phase-7.6). Demo-critical.

``prov demo run --scenario <name>`` replays a fixed historical window as an ordered
sequence of screen states — each with the exact numbers that go on screen — at a
controllable speed. The sequence is what drives the live dashboard, and it is a pure
function of the seeded corpus: two runs of a scenario produce byte-identical steps and
identical numbers (the determinism the test gate asserts), and nothing here touches the
network (the offline test asserts that too — every figure comes from the frame, the
config, and, optionally, a locally trained model artefact).

Every number is computed, never written in (standing rule 1): the defect rate, the
KER11 verdict, the trust components all come from the audit, the adjudicator, and the
trust engine at replay time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from provenance.audit.orchestrator import run_audit
from provenance.detectors.base import AuditContext
from provenance.detectors.registry import run_detectors
from provenance.grid.coverage import build_coverage
from provenance.schema import canonical as C
from provenance.trust.engine import compute_trust, latest_timestamp

SCENARIOS: tuple[str, ...] = (
    "audit-headline",
    "ker11-adjudication",
    "contrast-fault",
    "deweathering-reveal",
    "explainability",
)

# Base dwell per step, in milliseconds, before the speed multiplier. A modelling choice
# for pacing, not a data value.
_BASE_DWELL_MS = 4000


def available_scenarios() -> tuple[str, ...]:
    return SCENARIOS


@dataclass(frozen=True, slots=True)
class DemoStep:
    index: int
    at_offset_ms: int
    screen: str
    headline: str
    numbers: dict[str, Any] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "at_offset_ms": self.at_offset_ms,
            "screen": self.screen,
            "headline": self.headline,
            "numbers": self.numbers,
            "reason_codes": self.reason_codes,
        }


@dataclass(frozen=True, slots=True)
class DemoScenario:
    name: str
    title: str
    window: dict[str, str]
    steps: list[DemoStep]

    def screen_states(self) -> list[str]:
        return [s.screen for s in self.steps]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "window": self.window,
            "steps": [s.to_dict() for s in self.steps],
        }


def _paced(specs: list[tuple[str, str, dict[str, Any], list[str]]], speed: float) -> list[DemoStep]:
    """Attach a monotonic, speed-scaled offset to each (screen, headline, numbers, codes)."""
    dwell = max(1, round(_BASE_DWELL_MS / max(speed, 1e-6)))
    return [
        DemoStep(
            index=i,
            at_offset_ms=i * dwell,
            screen=screen,
            headline=head,
            numbers=nums,
            reason_codes=codes,
        )
        for i, (screen, head, nums, codes) in enumerate(specs)
    ]


def _window(frame: pd.DataFrame) -> dict[str, str]:
    return {
        "start": pd.Timestamp(frame[C.TIMESTAMP].min()).isoformat(),
        "end": pd.Timestamp(frame[C.TIMESTAMP].max()).isoformat(),
    }


def build_scenario(
    name: str,
    frame: pd.DataFrame,
    station_meta: dict[str, Any],
    *,
    speed: float = 1.0,
) -> DemoScenario:
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario {name!r}; expected one of {list(SCENARIOS)}.")
    builder = {
        "audit-headline": _audit_headline,
        "ker11-adjudication": _ker11_adjudication,
        "contrast-fault": _contrast_fault,
        "deweathering-reveal": _deweathering_reveal,
        "explainability": _explainability,
    }[name]
    specs, title = builder(frame, station_meta)
    return DemoScenario(name=name, title=title, window=_window(frame), steps=_paced(specs, speed))


def build_all(
    frame: pd.DataFrame, station_meta: dict[str, Any], *, speed: float = 1.0
) -> dict[str, DemoScenario]:
    return {name: build_scenario(name, frame, station_meta, speed=speed) for name in SCENARIOS}


_Spec = tuple[str, str, dict[str, Any], list[str]]


def _audit_headline(frame: pd.DataFrame, _meta: dict[str, Any]) -> tuple[list[_Spec], str]:
    result = run_audit(frame)
    dr = result.defect_rate
    cov = result.coverage
    top = sorted(result.defects_by_code.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    specs: list[_Spec] = [
        ("title", "Is This Real?", {"tagline": "AI Trust Layer for Environmental Data"}, []),
        (
            "network-overview",
            "A network that looks perfectly healthy",
            {
                "n_readings": int(result.meta.n_rows),
                "conventional_completeness_pct": round(cov.conventional_completeness_pct, 4),
                "n_stations": int(cov.n_stations),
            },
            [],
        ),
        (
            "defect-headline",
            "…and isn't",
            {
                "defect_rate_pct": round(dr.percent, 4),
                "n_defective_cells": int(dr.n_defective_cells),
                "n_covered_cells": int(dr.n_covered_cells),
            },
            [],
        ),
        (
            "top-codes",
            "The genuine, well-formed, and wrong",
            {code: int(n) for code, n in top},
            [code for code, _ in top],
        ),
    ]
    return specs, "The audit headline"


def _pick_station(frame: pd.DataFrame) -> str:
    """The station carrying the most counting defects — the interesting one to explain."""
    from provenance.config.loading import load_thresholds
    from provenance.detectors.base import REASON_CODE

    ctx = AuditContext(thresholds=load_thresholds(), coverage=build_coverage(frame))
    defects = run_detectors(frame, ctx)
    fallback = str(sorted(frame[C.STATION_ID].unique())[0])
    if defects.empty:
        return fallback
    counts = defects[defects[REASON_CODE].notna()][C.STATION_ID].value_counts()
    return str(counts.index[0]) if len(counts) else fallback


def _explainability(frame: pd.DataFrame, _meta: dict[str, Any]) -> tuple[list[_Spec], str]:
    from provenance.config.loading import load_thresholds

    station = _pick_station(frame)
    coverage = build_coverage(frame)
    ctx = AuditContext(thresholds=load_thresholds(), coverage=coverage)
    defects = run_detectors(frame, ctx)
    at = latest_timestamp(frame)
    score = compute_trust(frame, defects, station, at, coverage=coverage)
    components = {c.name: round(c.value, 4) for c in score.components}
    specs: list[_Spec] = [
        (
            "station-select",
            f"Why does {station} score what it scores?",
            {"station_id": station},
            [],
        ),
        (
            "trust-score",
            "A number, never on its own",
            {"trust": round(score.value, 4), "risk": round(score.risk.value, 4)},
            [],
        ),
        ("components", "Its four components", components, []),
        (
            "reason-codes",
            "…and at least one reason",
            {"n_reason_codes": len(score.reason_codes)},
            list(score.reason_codes),
        ),
    ]
    return specs, "Explainability — a trust score with its reasons"


def _adjudications(frame: pd.DataFrame, meta: dict[str, Any], *, limit: int):  # type: ignore[no-untyped-def]
    from provenance.graph.replay import replay_frame

    if not meta:
        return []
    return replay_frame(frame, dict(meta), limit=limit)


def _ker11_adjudication(frame: pd.DataFrame, meta: dict[str, Any]) -> tuple[list[_Spec], str]:
    adjudications = _adjudications(frame, meta, limit=1)
    if not adjudications:
        return (
            [("no-event", "No candidate event in this window", {}, [])],
            "Graph adjudication",
        )
    adj = adjudications[0]
    ev = adj.event
    bundle = adj.evidence
    n_downwind = bundle.n_downwind if bundle is not None else 0
    n_usable = bundle.n_usable if bundle is not None else 0
    specs: list[_Spec] = [
        (
            "event-appears",
            f"{ev.station_id} · {ev.parameter} spikes",
            {
                "station_id": ev.station_id,
                "parameter": ev.parameter,
                "value": round(float(ev.value), 2),
                "excess": round(float(ev.excess), 2),
            },
            [],
        ),
        (
            "neighbours",
            "What do the neighbours say?",
            {"n_downwind": n_downwind, "n_usable": n_usable},
            [],
        ),
        (
            "verdict",
            "The adjudicator's call",
            {
                "verdict": adj.verdict.value,
                "confidence": round(float(adj.confidence), 3),
                "confidence_band": adj.confidence_band.value,
                "routes_to_review": adj.routes_to_review,
            },
            [],
        ),
    ]
    return specs, "KER11 — is this spike real?"


def _contrast_fault(frame: pd.DataFrame, meta: dict[str, Any]) -> tuple[list[_Spec], str]:
    adjudications = _adjudications(frame, meta, limit=8)
    if not adjudications:
        return ([("no-event", "No candidate events to contrast", {}, [])], "Contrast")
    lead = adjudications[0]
    # A contrasting event with a different verdict, else the next-ranked event.
    contrast = next((a for a in adjudications[1:] if a.verdict != lead.verdict), None) or (
        adjudications[1] if len(adjudications) > 1 else None
    )

    def _card(a) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "station_id": a.event.station_id,
            "parameter": a.event.parameter,
            "verdict": a.verdict.value,
            "confidence": round(float(a.confidence), 3),
        }

    specs: list[_Spec] = [
        ("lead-event", "Same shape on the screen", _card(lead), []),
        (
            "contrast-verdicts",
            "Different verdicts",
            {"a": _card(lead), "b": _card(contrast) if contrast is not None else None},
            [],
        ),
    ]
    return specs, "Contrast — the number looks the same either way"


def _deweathering_reveal(frame: pd.DataFrame, _meta: dict[str, Any]) -> tuple[list[_Spec], str]:
    station = _pick_station(frame)
    # Raw level statistics are always available; the deweathered residual needs the
    # trained model, and degrades to a clear note when it is absent (standing rule 6).
    raw = pd.to_numeric(frame[frame[C.STATION_ID] == station][C.VALUE], errors="coerce").dropna()
    model_available = False
    note = "Deweathering model not loaded — showing raw levels only (graceful degradation)."
    try:
        from provenance.models import registry

        model_available = registry.load_bundle() is not None
        if model_available:
            note = "Deweathered residual available from the trained model."
    except Exception:
        model_available = False

    specs: list[_Spec] = [
        (
            "station-raw",
            f"{station} — raw levels",
            {"n_readings": len(raw), "mean": round(float(raw.mean()) if len(raw) else 0.0, 3)},
            [],
        ),
        (
            "deweather",
            "Strip the weather, keep the signal",
            {"model_available": model_available, "note": note},
            [],
        ),
    ]
    return specs, "Deweathering — separating weather from fault"
