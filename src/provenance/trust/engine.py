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
    exposure: float | None = None,
    imputation_modelled: float | None = None,
) -> TrustScore:
    """Compute the trust score for ``station_id`` at ``at`` over a trailing window.

    ``exposure`` is the PopulationExposure multiplier for this station, computed from
    the GTFS transit-corridor layer (:mod:`provenance.grid.exposure`). When it is
    ``None`` — no GTFS bundle, or no coordinate for this station — the factor falls
    back to the neutral 1.0 and the score reports ``population_exposure_stubbed=True``
    (graceful degradation, standing rule 6). When it is provided the flag is False:
    the exposure is measured, not stubbed.

    ``imputation_modelled`` is the trained imputation model's calibrated uncertainty
    (§7.2) for this station/window, already normalised to [0, 1)
    (:mod:`provenance.models.hstgat.imputation_serving`), or ``None`` when no model
    covers this station's parameters — then the term falls back to the raw
    absent-fraction placeholder, exactly as before the model existed.
    """
    thresholds = thresholds or load_thresholds()
    weights_cfg = weights_cfg or load_trust_weights()
    coverage = coverage or build_coverage(frame)
    at = pd.Timestamp(at)
    w = weights_cfg["weights"]

    health, rc_h, notes_h = comp.health_conf(defects, coverage, station_id, at, weights_cfg)
    imput, rc_i, notes_i = comp.imputation_uncertainty(
        coverage, station_id, at, weights_cfg, modelled=imputation_modelled
    )
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
    if exposure is None:
        stubbed = True
        exposure_factor = float(weights_cfg["risk"]["population_exposure_stub"])
    else:
        stubbed = False
        exposure_factor = float(exposure)
    risk = Risk(
        value=round(total * svt * exposure_factor, 6),
        trust=total,
        severity_vs_threshold=svt,
        population_exposure=exposure_factor,
        population_exposure_stubbed=stubbed,
    )
    if stubbed:
        # Kept byte-identical to the phase-2 wording on purpose: the station-detail
        # panel renders this note, and the pinned visual baselines were captured with
        # it. The demo corpus carries no GTFS bundle, so this is the note that shows;
        # changing it churns the baselines for no product reason.
        notes.append("PopulationExposure is stubbed at 1.0 until GTFS ridership lands (§7.8).")
    else:
        notes.append(
            f"PopulationExposure {exposure_factor:g} from the GTFS transit-corridor layer (§7.8)."
        )

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
    """Re-stamp a component with its elicited weight, carrying everything else.

    ``evidence`` has to be copied across explicitly: this rebuilds the frozen
    dataclass field by field, so anything omitted here is silently dropped between
    the component that measured it and the score that reports it.
    """
    return TrustComponent(
        name=c.name,
        value=c.value,
        weight=weight,
        is_placeholder=c.is_placeholder,
        detail=c.detail,
        evidence=dict(c.evidence),
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


def scoring_instants(
    frame: pd.DataFrame, *, cadence_hours: int = 24, max_points: int = 120
) -> list[pd.Timestamp]:
    """The timestamps at which to score a station across the ingest window.

    Anchored on the most recent reading and stepped backwards at ``cadence_hours``
    to the first reading, capped at ``max_points`` (keeping the most recent), then
    returned in ascending order. This is what turns the trust series from a single
    point into a real trajectory (flag-review resolution for standing rule 9's
    "series" endpoint).
    """
    end = latest_timestamp(frame)
    start = pd.Timestamp(frame[C.TIMESTAMP].min())
    step = pd.Timedelta(hours=max(1, cadence_hours))
    instants: list[pd.Timestamp] = []
    t = end
    while t >= start and len(instants) < max_points:
        instants.append(t)
        t = t - step
    return sorted(set(instants))
