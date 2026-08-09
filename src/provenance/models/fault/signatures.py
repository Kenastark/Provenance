"""Realistic fault signatures injected over known-good windows, for training.

The classifier learns from synthetic faults stamped onto the clean weather corpus,
each with a ground-truth label. The four signatures the phase names map to how a real
sensor fails:

* **flatline** — a stuck sensor reporting one value forever → FROZEN (caught by the
  deterministic zero-variance rule R12).
* **dropout** — the station stops transmitting for a stretch → COMMUNICATION_FAILURE
  (caught by the comm-gap rule R02).
* **gain error** — a scaling/decimal fault that blows the reading past what physics
  allows → PHYSICALLY_IMPOSSIBLE (caught by the bounds rule R07/R08).
* **drift ramp** — a slow calibration drift that stays *inside* physical bounds →
  CALIBRATION_DRIFT, the subtle case only the model can see.

Everything is seeded and deterministic. Injections are spread across stations and the
whole time span (not clustered early) so a forward-chaining split still has faults in
its held-out block to score.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from provenance.models.fault.labels import FaultClass
from provenance.schema import canonical as C


@dataclass(frozen=True, slots=True)
class Injection:
    """One injected fault: its signature, where it landed, and its true class."""

    kind: str
    station_id: str
    parameter: str
    fault_class: FaultClass
    timestamps: tuple[pd.Timestamp, ...]
    """The affected cell timestamps. For a dropout these are the *removed* hours (no
    cell survives to carry a label; recall is scored by whether R02 fires on the gap)."""


@dataclass(frozen=True, slots=True)
class LabeledCorpus:
    """A faulty frame plus the ground truth: every injection and every cell's class."""

    frame: pd.DataFrame
    injections: tuple[Injection, ...]
    cell_labels: dict[tuple[str, str, pd.Timestamp], FaultClass]


# Pollutant series are the injection targets (meteorology is left clean so the feature
# side stays honest). Each entry is (station_index, parameter).
_DRIFT_TARGETS = ((0, "PM10"), (2, "NO2"), (4, "O3"), (1, "CO"), (3, "PM10"))
_GAIN_TARGETS = ((1, "PM10"), (3, "NO2"), (5, "O3"))
_DROPOUT_TARGETS = ((2, "CO"), (4, "PM10"), (0, "NO2"))
_FLATLINE_TARGETS = ((5, "PM10"), (3, "O3"))

_GAIN_FACTOR = 100.0  # a decimal-point / scaling fault: pushes the value past its max.
_DROPOUT_HOURS = 10  # > comm_gap min (6h), so R02 fires.
_DRIFT_HOURS = 60  # a slow ramp long enough to show a sustained residual trend.


def build_labeled_corpus(
    clean_frame: pd.DataFrame,
    *,
    seed: int = 20260907,
) -> LabeledCorpus:
    """Inject the four fault signatures into ``clean_frame`` and return the ground truth.

    ``clean_frame`` is a weather-coupled corpus (see ``fixtures.weather``). The returned
    frame is canonical and re-validated. Meteorological-artefact labels are *not* set
    here — they are derived from the deweather residual downstream, because "explained
    by weather" is a statement about the residual, not something to stamp on raw values.
    """
    rng = np.random.RandomState(seed)
    stations = sorted(clean_frame[C.STATION_ID].astype(str).unique())
    times = pd.DatetimeIndex(sorted(clean_frame[C.TIMESTAMP].unique()))
    n_hours = len(times)

    def _spread_start(i: int, k: int, window: int, trailing_margin: int = 0) -> int:
        """Evenly place instance ``i`` of ``k`` across the timeline, last one near the end.

        Guarantees the final instance of each signature lands in the last time block, so
        a forward-chaining held-out split always has that signature to score.
        ``trailing_margin`` keeps a stretch of readings *after* the last instance — a
        dropout needs surviving rows on both sides, or the coverage grid ends at the gap
        and the missing hours read as "series stopped", not "communication failure"."""
        max_start = max(0, n_hours - window - trailing_margin)
        return round(i * max_start / max(1, k - 1))

    # Work on a mutable per-(station,parameter) value map and a drop set.
    frame = clean_frame.copy()
    injections: list[Injection] = []
    cell_labels: dict[tuple[str, str, pd.Timestamp], FaultClass] = {}
    drop_keys: set[tuple[str, str, pd.Timestamp]] = set()

    def _series_index(station: str, parameter: str) -> pd.Index:
        return frame.index[(frame[C.STATION_ID] == station) & (frame[C.PARAMETER] == parameter)]

    def _station(s_ix: int) -> str | None:
        """Resolve a target's station index, skipping targets a small corpus lacks."""
        return stations[s_ix] if s_ix < len(stations) else None

    # --- drift ramps → CALIBRATION_DRIFT (subtle; must stay in bounds) ---------
    for i, (s_ix, parameter) in enumerate(_DRIFT_TARGETS):
        station = _station(s_ix)
        if station is None:
            continue
        idx = _series_index(station, parameter)
        if len(idx) < _DRIFT_HOURS + 2:
            continue
        start = _spread_start(i, len(_DRIFT_TARGETS), _DRIFT_HOURS)
        window = idx[start : start + _DRIFT_HOURS]
        base = float(frame.loc[window, C.VALUE].mean())
        slope = 0.9 * base / _DRIFT_HOURS  # reaches ~+90% of baseline: clear, still bounded
        ramp = slope * np.arange(len(window))
        frame.loc[window, C.VALUE] = frame.loc[window, C.VALUE].to_numpy() + ramp
        ts_list = tuple(pd.Timestamp(t) for t in frame.loc[window, C.TIMESTAMP])
        injections.append(
            Injection("drift", station, parameter, FaultClass.CALIBRATION_DRIFT, ts_list)
        )
        for t in ts_list:
            cell_labels[(station, parameter, t)] = FaultClass.CALIBRATION_DRIFT

    # --- gain errors → PHYSICALLY_IMPOSSIBLE (rule R07 catches the overshoot) --
    for s_ix, parameter in _GAIN_TARGETS:
        station = _station(s_ix)
        if station is None:
            continue
        idx = _series_index(station, parameter)
        if len(idx) < 6:
            continue
        # Three random cells plus one guaranteed near the end (so a held-out block scores it).
        picks = set(rng.choice(range(1, len(idx) - 1), size=3, replace=False).tolist())
        picks.add(len(idx) - 2)
        cells = idx[sorted(picks)]
        frame.loc[cells, C.VALUE] = frame.loc[cells, C.VALUE].to_numpy() * _GAIN_FACTOR
        ts_list = tuple(pd.Timestamp(t) for t in frame.loc[cells, C.TIMESTAMP])
        injections.append(
            Injection("gain", station, parameter, FaultClass.PHYSICALLY_IMPOSSIBLE, ts_list)
        )
        for t in ts_list:
            cell_labels[(station, parameter, t)] = FaultClass.PHYSICALLY_IMPOSSIBLE

    # --- dropouts → COMMUNICATION_FAILURE (rows removed; R02 fires on the gap) -
    for i, (s_ix, parameter) in enumerate(_DROPOUT_TARGETS):
        station = _station(s_ix)
        if station is None:
            continue
        idx = _series_index(station, parameter)
        if len(idx) < _DROPOUT_HOURS + 2:
            continue
        start = max(1, _spread_start(i, len(_DROPOUT_TARGETS), _DROPOUT_HOURS, trailing_margin=16))
        gap = idx[start : start + _DROPOUT_HOURS]
        ts_list = tuple(pd.Timestamp(t) for t in frame.loc[gap, C.TIMESTAMP])
        drop_keys.update((station, parameter, t) for t in ts_list)
        injections.append(
            Injection("dropout", station, parameter, FaultClass.COMMUNICATION_FAILURE, ts_list)
        )

    # --- flatlines → FROZEN (whole series frozen; R12 needs zero variance) -----
    for s_ix, parameter in _FLATLINE_TARGETS:
        station = _station(s_ix)
        if station is None:
            continue
        idx = _series_index(station, parameter)
        if len(idx) < 2:
            continue
        frozen_value = float(frame.loc[idx, C.VALUE].iloc[0])
        frame.loc[idx, C.VALUE] = frozen_value
        ts_list = tuple(pd.Timestamp(t) for t in frame.loc[idx, C.TIMESTAMP])
        injections.append(Injection("flatline", station, parameter, FaultClass.FROZEN, ts_list))
        for t in ts_list:
            cell_labels[(station, parameter, t)] = FaultClass.FROZEN

    if drop_keys:
        key = list(zip(frame[C.STATION_ID], frame[C.PARAMETER], frame[C.TIMESTAMP], strict=True))
        keep = [k not in drop_keys for k in key]
        frame = frame[keep]

    frame = _revalidate(frame)
    return LabeledCorpus(frame=frame, injections=tuple(injections), cell_labels=cell_labels)


def _revalidate(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.drop(columns=[C.ROW_HASH]).copy()
    out[C.VALUE] = out[C.VALUE].round(4)
    out = C.add_row_hash(out)
    return C.validate(out)
