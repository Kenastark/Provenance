"""The learned propagation expectation — HST-GAT in place of the analytic plume prior.

This is phase-6 item 4: swap the analytic expectation the phase-4 adjudicator judges
neighbours against for the HST-GAT's graph-conditioned forecast, **behind a feature
flag and with an automatic analytic fallback** (standing rule 6). The mechanism is the
masked-autoencoder the model was trained on: to ask "what should the network expect at
neighbour *j* the hour after the event?", hide every station's value at that hour and
let the model reconstruct it from its wind-weighted neighbours (including the elevated
source) and each station's own history. The reconstruction *is* the graph-conditioned
expectation, with a predictive σ that feeds the calibrated interval (§7.7).

The layering holds because this module lives in ``models`` and only *implements* the
``graph.ExpectationProvider`` Protocol; ``graph`` never imports it. The adjudicator gets
a provider injected and records its ``provenance`` in the evidence bundle, so a human
always sees whether a verdict came from the learned model or the analytic fallback.

No propagation accuracy is computed anywhere here (standing rule 4): this returns a
per-neighbour expected excess and a σ, nothing that could be read as a method score.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from provenance.graph.adjudicate import CandidateEvent
from provenance.graph.edges import WindEdgeParams
from provenance.graph.expectation import (
    LEARNED,
    AnalyticExpectation,
    ExpectationProvider,
    NeighbourExpectation,
)
from provenance.graph.propagation import PropagationParams, evaluation_hours
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField, WindVector
from provenance.models.hstgat.data import build_batch
from provenance.models.hstgat.store import LoadedModel, load_latest
from provenance.schema import canonical as C


def _series(readings: pd.DataFrame, station_id: str, parameter: str) -> pd.Series:
    rows = readings[(readings[C.STATION_ID] == station_id) & (readings[C.PARAMETER] == parameter)]
    if rows.empty:
        return pd.Series(dtype="float64")
    s = rows.set_index(C.TIMESTAMP)[C.VALUE].astype("float64").sort_index()
    return s[~s.index.duplicated(keep="last")]


def _baseline(series: pd.Series, before: pd.Timestamp, window_hours: int) -> float | None:
    if series.empty:
        return None
    start = before - pd.Timedelta(hours=window_hours)
    prior = series[(series.index >= start) & (series.index < before)]
    if prior.empty:
        prior = series[series.index < before]
    if prior.empty:
        return None
    return float(np.median(prior.to_numpy()))


@dataclass(frozen=True, slots=True)
class LearnedExpectation:
    """An :class:`ExpectationProvider` backed by the HST-GAT forecast for one event.

    Geometry and timing (distance, bearing, arrival delay, horizon) are still the
    honest analytic quantities — the model does not predict travel time — but the
    *expected excess* at each neighbour, and its σ, come from the learned reconstruction.
    Any neighbour the model cannot forecast (not an env station it covers) falls back to
    the analytic expected excess for that neighbour, transparently.
    """

    provenance: str
    predicted: dict[str, tuple[float, float]]  # station_id -> (physical mean, physical sigma)
    baselines: dict[str, float]
    conformal_q: float | None = None
    """The persisted split-conformal half-width multiplier (normalised score). ``None``
    when the model was saved without a calibrator — then no interval is attached."""
    _analytic: AnalyticExpectation = field(default_factory=AnalyticExpectation)

    def _interval(self, expected_excess: float, sigma: float) -> tuple[float, float] | None:
        """Calibrated interval on the expected excess: ``expected_excess ± q·σ``.

        Returns ``None`` unless a finite conformal ``q`` was persisted with the model, so
        the interval is never fabricated from an un-calibrated width.
        """
        if self.conformal_q is None or not math.isfinite(self.conformal_q):
            return None
        half = self.conformal_q * sigma
        return (expected_excess - half, expected_excess + half)

    def expect(
        self,
        source: StationPoint,
        neighbour: StationPoint,
        wind: WindVector,
        event: CandidateEvent,
        wind_params: WindEdgeParams,
        prop_params: PropagationParams,
    ) -> NeighbourExpectation:
        geom = self._analytic.expect(source, neighbour, wind, event, wind_params, prop_params)
        pred = self.predicted.get(neighbour.station_id)
        base = self.baselines.get(neighbour.station_id)
        if pred is None or base is None:
            # Learned forecast unavailable for this neighbour → analytic excess, marked.
            return NeighbourExpectation(
                station_id=geom.station_id,
                distance_km=geom.distance_km,
                bearing_deg=geom.bearing_deg,
                arrival_delay_min=geom.arrival_delay_min,
                expected_excess=geom.expected_excess,
                within_horizon=geom.within_horizon,
                sigma=None,
            )
        mean_value, sigma_value = pred
        expected_excess = mean_value - base
        return NeighbourExpectation(
            station_id=geom.station_id,
            distance_km=geom.distance_km,
            bearing_deg=geom.bearing_deg,
            arrival_delay_min=geom.arrival_delay_min,
            expected_excess=expected_excess,
            within_horizon=geom.within_horizon,
            sigma=sigma_value,
            interval=self._interval(expected_excess, sigma_value),
        )


def forecast_at_hour(
    loaded: LoadedModel,
    frame: pd.DataFrame,
    points: list[StationPoint],
    wind: WindField,
    cfg: dict[str, Any],
    eval_time: pd.Timestamp,
) -> dict[str, tuple[float, float]]:
    """Graph-conditioned expected value + σ per env station at ``eval_time``.

    Hides every station's value at ``eval_time`` and reconstructs it from neighbours and
    history — the model's expectation for that hour given the rest of the network. Values
    are de-standardised with the trained constants back to the physical unit.
    """
    import torch

    batch = build_batch(
        frame,
        points,
        wind,
        cfg,
        target_parameter=loaded.target_parameter,
        mean=loaded.mean,
        std=loaded.std,
    )
    if eval_time not in batch.times:
        return {}
    t = batch.times.index(eval_time)
    hidden = torch.zeros_like(batch.target, dtype=torch.bool)
    hidden[t] = batch.observed[t]  # hide the whole eval hour, where observed
    value_input = torch.where(hidden, torch.zeros_like(batch.target), batch.target)
    mask_flag = hidden.to(batch.target.dtype)
    with torch.no_grad():
        fc = loaded.model(value_input, mask_flag, batch, return_attention_step=t)
    mean_std = fc.mean[t].numpy()
    sigma_std = np.sqrt(fc.variance[t].numpy())
    out: dict[str, tuple[float, float]] = {}
    for i, sid in enumerate(batch.env_ids):
        out[sid] = (
            float(mean_std[i] * loaded.std + loaded.mean),
            float(sigma_std[i] * loaded.std),
        )
    return out


def build_learned_provider(
    loaded: LoadedModel,
    frame: pd.DataFrame,
    points: list[StationPoint],
    wind: WindField,
    cfg: dict[str, Any],
    event: CandidateEvent,
    *,
    baseline_window_hours: int,
) -> ExpectationProvider:
    """A per-event learned provider, or the analytic one when the model cannot forecast.

    Falls back to :class:`AnalyticExpectation` (provenance "analytic") when the event's
    parameter is not the model's target, or the evaluation hour is outside the corpus —
    the honest degradation, never a silent guess.
    """
    if event.parameter != loaded.target_parameter:
        return AnalyticExpectation()
    prop_params = PropagationParams.from_config(cfg)
    hours = evaluation_hours(event.timestamp, prop_params)
    eval_time = hours[0]
    predicted = forecast_at_hour(loaded, frame, points, wind, cfg, eval_time)
    if not predicted:
        return AnalyticExpectation()
    baselines: dict[str, float] = {}
    for sid in predicted:
        base = _baseline(
            _series(frame, sid, event.parameter), event.timestamp, baseline_window_hours
        )
        if base is not None:
            baselines[sid] = base
    q = None
    if loaded.conformal is not None:
        raw_q = loaded.conformal.get("q")
        q = None if raw_q is None else float(raw_q)
    return LearnedExpectation(
        provenance=LEARNED, predicted=predicted, baselines=baselines, conformal_q=q
    )


def learned_provider_factory(
    frame: pd.DataFrame,
    points: list[StationPoint],
    wind: WindField,
    cfg: dict[str, Any],
    *,
    baseline_window_hours: int,
    artefacts_dir: Path | None = None,
) -> Callable[[CandidateEvent], ExpectationProvider]:
    """A factory ``event -> ExpectationProvider`` for the adjudicator, behind the flag.

    Loads the latest HST-GAT once. If no artefact exists (or it fails its card check
    upstream), returns a factory that always yields the analytic provider — so turning
    the feature flag on with no trained model degrades gracefully to phase-4 behaviour
    and the bundle records "analytic" (standing rule 6).
    """
    loaded = load_latest(artefacts_dir=artefacts_dir)
    if loaded is None:
        return lambda _event: AnalyticExpectation()

    def factory(event: CandidateEvent) -> ExpectationProvider:
        return build_learned_provider(
            loaded, frame, points, wind, cfg, event, baseline_window_hours=baseline_window_hours
        )

    return factory
