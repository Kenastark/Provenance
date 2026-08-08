"""The trust engine: canonical frame + defects → a fully-explained trust score.

This is the seam between the statistics layer and everything that consumes trust.
It computes the four §7.8 components, applies the elicited weights, assembles the
Risk figure (with PopulationExposure stubbed and flagged), and returns a
:class:`TrustScore` — which by construction cannot exist without its component
breakdown and reason codes.

Graceful degradation (standing rule 6): this layer *is* the statistics fallback.
It never needs a model artefact, so it always produces a score; when a caller
signals a missing downstream model, ``degraded=True`` is threaded through so the
response says the score came from statistics alone.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from provenance.config.loading import load_thresholds
from provenance.grid.coverage import CoverageModel, build_coverage
from provenance.schema import canonical as C
from provenance.trust import components as comp
from provenance.trust.score import Risk, TrustComponent, TrustScore
from provenance.trust.weights import load_trust_weights


def compute_trust(
    frame: pd.DataFrame,
    defects: pd.DataFrame,
    station_id: str,
    at: pd.Timestamp,
    *,
    coverage: CoverageModel | None = None,
    thresholds: dict[str, Any] | None = None,
    weights_cfg: dict[str, Any] | None = None,
    degraded: bool = False,
) -> TrustScore:
    """Compute the trust score for ``station_id`` at ``at`` over a trailing window."""
    thresholds = thresholds or load_thresholds()
    weights_cfg = weights_cfg or load_trust_weights()
    coverage = coverage or build_coverage(frame)
    at = pd.Timestamp(at)
    w = weights_cfg["weights"]

    health, rc_h, notes_h = comp.health_conf(defects, station_id, at, weights_cfg)
    imput, rc_i, notes_i = comp.imputation_uncertainty(coverage, station_id, at, weights_cfg)
    cross, rc_c, notes_c = comp.cross_sensor_consistency(
        frame, coverage, station_id, at, weights_cfg
    )
    phys, rc_p, notes_p = comp.physical_plausibility(
        frame, station_id, at, thresholds, defects, weights_cfg
    )

    weighted = [
        _weighted(health, float(w["health_conf"])),
        _weighted(imput, float(w["imputation_certainty"])),
        _weighted(cross, float(w["cross_sensor_consistency"])),
        _weighted(phys, float(w["physical_plausibility"])),
    ]
    total = sum(c.contribution for c in weighted)
    total = float(min(max(total, 0.0), 1.0))

    reason_codes = _dedupe(rc_h + rc_i + rc_c + rc_p)
    if not reason_codes:
        reason_codes = ["T00"]  # nominal: a score is never a bare number
    notes = notes_h + notes_i + notes_c + notes_p

    svt = comp.severity_vs_threshold(defects, station_id, at, weights_cfg)
    exposure = float(weights_cfg["risk"]["population_exposure_stub"])
    risk = Risk(
        value=round(total * svt * exposure, 6),
        trust=total,
        severity_vs_threshold=svt,
        population_exposure=exposure,
        population_exposure_stubbed=True,
    )
    notes.append("PopulationExposure is stubbed at 1.0 until GTFS ridership lands (§7.8).")

    return TrustScore(
        station_id=station_id,
        timestamp_utc=at.isoformat(),
        value=total,
        components=weighted,
        reason_codes=reason_codes,
        risk=risk,
        degraded=degraded,
        notes=notes,
    )


def _weighted(c: TrustComponent, weight: float) -> TrustComponent:
    return TrustComponent(
        name=c.name,
        value=c.value,
        weight=weight,
        is_placeholder=c.is_placeholder,
        detail=c.detail,
    )


def _dedupe(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def latest_timestamp(frame: pd.DataFrame) -> pd.Timestamp:
    """The most recent reading time in the frame — the default scoring instant."""
    return pd.Timestamp(frame[C.TIMESTAMP].max())
