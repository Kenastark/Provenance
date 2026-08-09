"""The four statistics-only trust components (blueprint §7.8).

Each function is pure over the canonical frame plus the audit's DefectFrame and
returns a :class:`TrustComponent` together with the reason codes and notes it
justifies. The engine weights and sums them. Everything is computed over a
trailing window ending at the reference timestamp so the score reflects the
station's *recent* condition, not its whole history.

The imputation term is an explicit placeholder: it has no model behind it, only a
neighbour-availability heuristic, and it is marked ``is_placeholder=True`` so a
consumer can never mistake it for a calibrated confidence (§7.8, standing rule 6).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from provenance.detectors.base import REASON_CODE, SEVERITY
from provenance.grid.coverage import CoverageModel
from provenance.schema import canonical as C
from provenance.trust.score import TrustComponent

_ComponentResult = tuple[TrustComponent, list[str], list[str]]


def _window_mask(ts: pd.Series, at: pd.Timestamp, window_hours: int) -> pd.Series:
    start = at - pd.Timedelta(hours=window_hours)
    return (ts > start) & (ts <= at)


def health_conf(
    defects: pd.DataFrame,
    station_id: str,
    at: pd.Timestamp,
    cfg: dict[str, Any],
) -> _ComponentResult:
    """Confidence from active defects in the trailing window, weighted by severity.

    HealthConf = exp(-load / scale), where load is the severity-weighted count of
    defect-counting flags on this station in the window. Clean → 1.0; a run of
    critical flags drives it toward 0.
    """
    hcfg = cfg["health"]
    severity_weights: dict[str, float] = hcfg["severity_weights"]
    scale = float(hcfg["decay_scale"])
    window_hours = int(hcfg["window_hours"])

    reason_codes: list[str] = []
    load = 0.0
    n_active = 0
    if not defects.empty:
        rows = defects[defects[C.STATION_ID] == station_id]
        if not rows.empty:
            in_window = rows[_window_mask(rows[C.TIMESTAMP], at, window_hours)]
            for _, r in in_window.iterrows():
                load += float(severity_weights.get(str(r[SEVERITY]), 0.2))
                n_active += 1
    value = float(np.exp(-load / scale)) if scale > 0 else (1.0 if load == 0 else 0.0)
    if n_active:
        reason_codes.append("T01")
    return (
        TrustComponent(
            name="HealthConf",
            value=value,
            weight=0.0,
            detail=f"{n_active} active flags",
            # T01's sentence asks for {n_defects}. Carrying the count, and not only
            # the prose above, is what lets the UI render it as a sentence.
            evidence={"n_defects": n_active},
        ),
        reason_codes,
        [],
    )


def imputation_uncertainty(
    coverage: CoverageModel,
    station_id: str,
    at: pd.Timestamp,
    cfg: dict[str, Any],
) -> _ComponentResult:
    """Placeholder uncertainty term. 1.0 for absent readings, relieved by neighbours.

    There is no imputation model in v1. This measures the fraction of the station's
    covered cells that are absent in the window and relieves it partially where
    neighbours still cover the same parameter. The component reports
    ``1 - uncertainty`` and is always flagged as a placeholder.
    """
    icfg = cfg["imputation"]
    window_hours = int(icfg["window_hours"])
    relief = float(icfg["neighbour_relief"])

    grids = [g for (s, _), g in coverage.series_grids.items() if s == station_id]
    expected = 0
    absent = 0
    params = set()
    for g in grids:
        params.add(g.parameter)
        for ts in [g.start + i * g.cadence for i in range(g.n_expected)]:
            if not (at - pd.Timedelta(hours=window_hours) < ts <= at):
                continue
            expected += 1
        absent += sum(
            1 for ts in g.absent_timestamps if at - pd.Timedelta(hours=window_hours) < ts <= at
        )
    if expected == 0:
        uncertainty = 0.0
    else:
        raw = absent / expected
        # Neighbour availability: fraction of this station's parameters that other
        # stations also carry. A fully covered parameter set relieves up to `relief`.
        neighbour_frac = _neighbour_fraction(coverage, station_id, params)
        uncertainty = raw * (1.0 - relief * neighbour_frac)
    uncertainty = float(min(max(uncertainty, 0.0), 1.0))
    certainty = 1.0 - uncertainty

    # T02 explains the placeholder only when the term actually bites (some absence).
    # A fully-present station carries no imputation caveat.
    reason_codes: list[str] = []
    notes: list[str] = []
    pct = round(100.0 * uncertainty, 1)
    if uncertainty > 0.0:
        reason_codes.append("T02")
        notes.append(f"ImputationUncertainty is a placeholder term ({pct}% absent); no model yet.")
    return (
        TrustComponent(
            name="ImputationCertainty",
            value=certainty,
            weight=0.0,
            is_placeholder=True,
            detail=f"imputation uncertainty {pct}% (placeholder, no model)",
            evidence={"pct": pct},  # T02
        ),
        reason_codes,
        notes,
    )


def _neighbour_fraction(coverage: CoverageModel, station_id: str, params: set[str]) -> float:
    if not params:
        return 0.0
    covered = 0
    for p in params:
        others = {s for (s, q) in coverage.series_grids if q == p and s != station_id}
        if others:
            covered += 1
    return covered / len(params)


def cross_sensor_consistency(
    frame: pd.DataFrame,
    coverage: CoverageModel,
    station_id: str,
    at: pd.Timestamp,
    cfg: dict[str, Any],
) -> _ComponentResult:
    """Spearman rank agreement with the k nearest peers sharing each parameter.

    Averaged over the station's parameters. A constant (frozen) target series
    cannot track its neighbours and scores 0 for that parameter; where too few
    peers exist, consistency is *unavailable* (neutral 0.5, T05), not zero.
    """
    from scipy.stats import spearmanr

    ccfg = cfg["cross_sensor"]
    window_hours = int(ccfg["window_hours"])
    k = int(ccfg["k_neighbours"])
    min_peers = int(ccfg["min_peers"])

    fw = frame[_window_mask(frame[C.TIMESTAMP], at, window_hours)]
    station_params = sorted(fw[fw[C.STATION_ID] == station_id][C.PARAMETER].unique())
    if not station_params:
        return (
            TrustComponent(
                name="CrossSensorConsistency",
                value=0.5,
                weight=0.0,
                detail="no data",
                evidence={"n": 0, "min_peers": min_peers},
            ),
            ["T05"],
            [],
        )

    scores: list[float] = []
    insufficient = False
    disagreement_peers = 0
    for parameter in station_params:
        target = _series_at(fw, station_id, parameter)
        peers = [s for (s, q) in coverage.series_grids if q == parameter and s != station_id]
        peers = sorted(peers)[:k]
        if len(peers) < min_peers:
            insufficient = True
            continue
        if target.nunique() <= 1:
            scores.append(0.0)  # frozen: cannot track neighbours
            disagreement_peers += len(peers)
            continue
        corrs: list[float] = []
        for peer in peers:
            peer_series = _series_at(fw, peer, parameter)
            joined = pd.concat([target, peer_series], axis=1, join="inner").dropna()
            if len(joined) < 3 or joined.iloc[:, 1].nunique() <= 1:
                continue
            rho = spearmanr(joined.iloc[:, 0], joined.iloc[:, 1]).statistic
            if not np.isnan(rho):
                corrs.append(float(rho))
        if corrs:
            mean_rho = float(np.mean(corrs))
            scores.append((mean_rho + 1.0) / 2.0)  # map [-1,1] -> [0,1]
            if mean_rho < 0.3:
                disagreement_peers += len(corrs)
        else:
            insufficient = True

    reason_codes: list[str] = []
    if not scores:
        value = 0.5
        reason_codes.append("T05")
    else:
        value = float(np.mean(scores))
        if disagreement_peers:
            reason_codes.append("T03")
        if insufficient:
            reason_codes.append("T05")
    return (
        TrustComponent(
            name="CrossSensorConsistency",
            value=value,
            weight=0.0,
            detail=f"{len(scores)} parameter(s) compared to peers",
            # T03 asks for {n} disagreeing neighbours; T05 for the {min_peers}
            # threshold it fell short of. Both are emitted unconditionally so the
            # sentence renders whichever of the two codes this component raised.
            evidence={"n": disagreement_peers, "min_peers": min_peers},
        ),
        reason_codes,
        [],
    )


def _series_at(frame: pd.DataFrame, station_id: str, parameter: str) -> pd.Series:
    g = frame[(frame[C.STATION_ID] == station_id) & (frame[C.PARAMETER] == parameter)]
    s = pd.Series(
        pd.to_numeric(g[C.VALUE], errors="coerce").to_numpy(),
        index=pd.to_datetime(g[C.TIMESTAMP]).to_numpy(),
    )
    return s[~s.index.duplicated(keep="first")].sort_index()


def physical_plausibility(
    frame: pd.DataFrame,
    station_id: str,
    at: pd.Timestamp,
    thresholds: dict[str, Any],
    defects: pd.DataFrame,
    cfg: dict[str, Any],
) -> _ComponentResult:
    """Distance from the physical bounds, plus the PM2.5 ≤ PM10 constraint.

    The worst (minimum) plausibility over the station's readings in the window
    drives the term: one impossible reading is enough to make a station's data
    untrustworthy. A reading within the safety margin of a bound already scores
    below 1.
    """
    pcfg = cfg["physical"]
    margin = float(pcfg["safety_margin_fraction"])
    bounds = thresholds["physical_bounds"]
    window_hours = int(cfg["health"]["window_hours"])

    fw = frame[_window_mask(frame[C.TIMESTAMP], at, window_hours)]
    g = fw[fw[C.STATION_ID] == station_id]
    plausibilities: list[float] = []
    for parameter, spec in bounds.items():
        series = pd.to_numeric(g[g[C.PARAMETER] == parameter][C.VALUE], errors="coerce").dropna()
        if series.empty:
            continue
        lo = spec.get("min")
        hi = spec.get("max")
        if lo is None or hi is None or hi <= lo:
            continue
        span = hi - lo
        # Soften only near the UPPER (dangerous) ceiling: normal values sit well
        # below it and score 1.0, while a reading crowding the physical maximum is
        # already partly implausible. Lower bounds are natural floors (e.g. 0), so
        # a small in-range value is not penalised.
        safe = margin * span
        for v in series:
            if v < lo or v > hi:
                plausibilities.append(0.0)
            elif safe > 0 and (hi - v) < safe:
                plausibilities.append(float((hi - v) / safe))
            else:
                plausibilities.append(1.0)

    value = min(plausibilities) if plausibilities else 1.0
    reason_codes: list[str] = []
    if not defects.empty:
        phys = defects[
            (defects[C.STATION_ID] == station_id)
            & (defects[REASON_CODE].isin(["R07", "R08", "R09"]))
        ]
        phys = phys[_window_mask(phys[C.TIMESTAMP], at, window_hours)]
        if not phys.empty:
            value = 0.0
            reason_codes.append("T04")
    elif value < 0.5:
        reason_codes.append("T04")
    return (
        TrustComponent(
            name="PhysicalPlausibility",
            value=value,
            weight=0.0,
            detail=f"worst-case margin over {len(plausibilities)} readings",
            # T04's sentence takes no placeholder, but the sample size is what makes
            # the term auditable, so it travels with the score rather than only in
            # the prose.
            evidence={"n_readings": len(plausibilities)},
        ),
        reason_codes,
        [],
    )


def severity_vs_threshold(
    defects: pd.DataFrame,
    station_id: str,
    at: pd.Timestamp,
    cfg: dict[str, Any],
) -> float:
    """How far the worst active defect's severity sits above nominal, for Risk.

    1.0 when clean; rises with the worst severity weight present in the window.
    """
    hcfg = cfg["health"]
    severity_weights: dict[str, float] = hcfg["severity_weights"]
    window_hours = int(hcfg["window_hours"])
    if defects.empty:
        return 1.0
    rows = defects[defects[C.STATION_ID] == station_id]
    rows = rows[_window_mask(rows[C.TIMESTAMP], at, window_hours)]
    if rows.empty:
        return 1.0
    worst = max(float(severity_weights.get(str(s), 0.2)) for s in rows[SEVERITY])
    return 1.0 + worst
