"""Offline replay: rank the corpus's candidate events, adjudicate each, write bundles.

This is the harness the B3 demo runs. It does not know, and must not assume, what
any event *is*: it ranks the audit's notable events by magnitude and anomaly,
adjudicates each over the wind graph, and writes a full evidence bundle per event
under ``reports/adjudications/``. Pointed at the real Green Sentinel drop, the
top-ranked event is the ~4,100 µg/m³ PM10 spike at KER11 — surfaced by ranking, not
named in code — and the second is the demo's backup case (§16 critique 9). Pointed
at a synthetic scenario, it produces the same bundles deterministically for CI.

No verdict is hardcoded, hinted at, or assumed anywhere here or in the tests that
drive it: the verdict is whatever the adjudicator returns for the evidence.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from provenance.audit.orchestrator import run_audit
from provenance.audit.result import NotableEvent
from provenance.config.loading import load_graph_config
from provenance.graph.adjudicate import (
    Adjudication,
    AdjudicatorParams,
    CandidateEvent,
    validate_event,
)
from provenance.graph.build import station_points_from_metadata
from provenance.graph.expectation import ExpectationProvider
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField
from provenance.schema import canonical as C


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    event: CandidateEvent
    magnitude: float
    source_code: str


def _station_series(frame: pd.DataFrame, station: str, parameter: str) -> pd.Series:
    rows = frame[(frame[C.STATION_ID] == station) & (frame[C.PARAMETER] == parameter)]
    if rows.empty:
        return pd.Series(dtype="float64")
    s = rows.set_index(C.TIMESTAMP)[C.VALUE].astype("float64").sort_index()
    return s[~s.index.duplicated(keep="last")]


def _baseline_before(series: pd.Series, before: pd.Timestamp, window_hours: int) -> float:
    if series.empty:
        return 0.0
    start = before - pd.Timedelta(hours=window_hours)
    prior = series[(series.index >= start) & (series.index < before)]
    if prior.empty:
        prior = series[series.index < before]
    if prior.empty:
        return float(np.median(series.to_numpy()))
    return float(np.median(prior.to_numpy()))


def build_candidate(
    frame: pd.DataFrame,
    station_id: str,
    parameter: str,
    timestamp: pd.Timestamp,
    *,
    window_hours: int,
    anomaly_score: float = 0.0,
    fallback_value: float | None = None,
) -> CandidateEvent | None:
    """A :class:`CandidateEvent` for a (station, parameter, timestamp) drawn from the frame.

    The value is the reading at that hour (or ``fallback_value`` when the cell is
    absent); the baseline is the station's own trailing median. Returns ``None`` when
    the station never carried the parameter.
    """
    ts = pd.Timestamp(timestamp)
    series = _station_series(frame, station_id, parameter)
    if series.empty:
        return None
    value = float(series.loc[ts]) if ts in series.index else fallback_value
    if value is None:
        return None
    baseline = _baseline_before(series, ts, window_hours)
    unit_rows = frame.loc[
        (frame[C.STATION_ID] == station_id) & (frame[C.PARAMETER] == parameter), C.UNIT
    ]
    unit = str(unit_rows.iloc[0]) if not unit_rows.empty else ""
    return CandidateEvent(
        station_id=station_id,
        parameter=parameter,
        timestamp=ts,
        value=value,
        baseline=baseline,
        anomaly_score=anomaly_score,
        unit=unit,
    )


def _candidate_from_event(
    frame: pd.DataFrame, event: NotableEvent, window_hours: int
) -> RankedCandidate | None:
    ev_val = event.evidence.get("value")
    candidate = build_candidate(
        frame,
        event.station_id,
        event.parameter,
        pd.Timestamp(event.timestamp_utc),
        window_hours=window_hours,
        anomaly_score=float(event.rank),
        fallback_value=float(ev_val) if ev_val is not None else None,
    )
    if candidate is None:
        return None
    return RankedCandidate(
        event=candidate, magnitude=candidate.excess, source_code=event.reason_code
    )


def rank_candidates(
    frame: pd.DataFrame, *, window_hours: int, limit: int | None = None
) -> list[RankedCandidate]:
    """Rank the audit's notable events by magnitude (excess) then anomaly rank.

    Magnitude wins because the demo leads with the largest anomaly; ties break on the
    audit's own ranking. Deterministic given the corpus.
    """
    result = run_audit(frame)
    candidates: list[RankedCandidate] = []
    for event in result.notable_events:
        cand = _candidate_from_event(frame, event, window_hours)
        if cand is not None:
            candidates.append(cand)
    candidates.sort(key=lambda c: (-c.magnitude, c.event.anomaly_score, c.event.station_id))
    if limit is not None:
        candidates = candidates[:limit]
    return candidates


def adjudicate_candidates(
    candidates: list[RankedCandidate],
    points: list[StationPoint],
    wind: WindField,
    frame: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    expectation_factory: Callable[[CandidateEvent], ExpectationProvider] | None = None,
) -> list[Adjudication]:
    """Adjudicate each candidate; optionally with a per-event learned expectation.

    ``expectation_factory`` is injected from the CLI (which may import ``models``) behind
    the learned-propagation feature flag, so ``graph`` still never imports ``models`` —
    it depends only on the ``ExpectationProvider`` Protocol. When ``None``, every event
    uses the analytic prior, exactly as phase 4.
    """
    return [
        validate_event(
            c.event,
            points,
            wind,
            frame,
            cfg,
            expectation=None if expectation_factory is None else expectation_factory(c.event),
        )
        for c in candidates
    ]


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def write_adjudications(adjudications: list[Adjudication], out_dir: Path) -> dict[str, Path]:
    """Write one JSON bundle per adjudication plus an index. Deterministic output."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    index: list[dict[str, Any]] = []
    for rank, adj in enumerate(adjudications, start=1):
        ev = adj.event
        name = f"adj_{rank:02d}_{_slug(ev.station_id)}_{_slug(ev.parameter)}_{_slug(ev.timestamp.isoformat())}.json"
        path = out_dir / name
        payload = {"rank": rank, **adj.to_dict()}
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        paths[name] = path
        index.append(
            {
                "rank": rank,
                "file": name,
                "station_id": ev.station_id,
                "parameter": ev.parameter,
                "timestamp_utc": ev.timestamp.isoformat(),
                "excess": round(ev.excess, 4),
                "verdict": adj.verdict.value,
                "confidence": round(adj.confidence, 4),
                "confidence_band": adj.confidence_band.value,
                "routes_to_review": adj.routes_to_review,
            }
        )
    index_path = out_dir / "index.json"
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    paths["index.json"] = index_path
    return paths


def replay_frame(
    frame: pd.DataFrame,
    station_meta: dict[str, Any],
    *,
    cfg: dict[str, Any] | None = None,
    limit: int | None = 10,
    expectation_factory: Callable[[CandidateEvent], ExpectationProvider] | None = None,
) -> list[Adjudication]:
    """Rank and adjudicate the candidate events in a canonical frame.

    ``expectation_factory`` (injected from the CLI behind the learned-propagation flag)
    swaps the analytic prior for the HST-GAT forecast per event; ``None`` is phase-4
    behaviour.
    """
    cfg = cfg or load_graph_config()
    params = AdjudicatorParams.from_config(cfg)
    points = station_points_from_metadata(station_meta)
    wind = WindField.from_frame(frame)
    candidates = rank_candidates(frame, window_hours=params.baseline_window_hours, limit=limit)
    return adjudicate_candidates(
        candidates, points, wind, frame, cfg, expectation_factory=expectation_factory
    )


def replay_path(
    data_dir: Path,
    out_dir: Path,
    *,
    limit: int = 10,
    expectation_factory: Callable[[CandidateEvent], ExpectationProvider] | None = None,
) -> list[Adjudication]:
    """Load a data drop, adjudicate its ranked events, and write the bundles.

    ``expectation_factory`` (built by the caller behind the learned-propagation flag)
    swaps the analytic prior for the HST-GAT forecast; ``None`` is phase-4 behaviour.
    """
    from provenance.io import loaders

    frame = loaders.load_data(data_dir)
    station_meta = loaders.load_station_metadata(data_dir)
    adjudications = replay_frame(
        frame, dict(station_meta), limit=limit, expectation_factory=expectation_factory
    )
    write_adjudications(adjudications, out_dir)
    return adjudications
