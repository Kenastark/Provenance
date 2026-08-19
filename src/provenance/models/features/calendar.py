"""Calendar features: the deterministic, source-free part of the feature matrix.

Hour-of-day, day-of-week and season are pure functions of the timestamp, so their
provenance is DERIVED, not measured — there is no sensor and no uncertainty. Each is
encoded on its natural cycle as ``(sin, cos)`` for the same reason wind direction is:
hour 23 and hour 0 are adjacent, and a raw integer hides that.

The boundary-layer-height proxy also lives here, because the honest stand-in we use
until the HungaroMet feed is confirmed is itself a time-of-day/season function (a
shallow nocturnal/winter mixing layer, a deep afternoon/summer one). It is flagged
PROXY, never MEASURED (§5.3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HOUR_SIN = "hour_sin"
HOUR_COS = "hour_cos"
DOW_SIN = "dow_sin"
DOW_COS = "dow_cos"
SEASON_SIN = "season_sin"
SEASON_COS = "season_cos"
BLH_PROXY = "boundary_layer_proxy"

_DAYS_PER_YEAR = 365.25


def _cyclic(values: np.ndarray, period: float) -> tuple[np.ndarray, np.ndarray]:
    radians = 2.0 * np.pi * values / period
    return np.sin(radians), np.cos(radians)


def calendar_features(timestamps: pd.DatetimeIndex) -> pd.DataFrame:
    """Hour/day-of-week/season sin-cos features for a timestamp index."""
    ts = pd.DatetimeIndex(timestamps)
    hour = ts.hour.to_numpy(dtype="float64")
    dow = ts.dayofweek.to_numpy(dtype="float64")
    doy = ts.dayofyear.to_numpy(dtype="float64")

    hour_sin, hour_cos = _cyclic(hour, 24.0)
    dow_sin, dow_cos = _cyclic(dow, 7.0)
    season_sin, season_cos = _cyclic(doy, _DAYS_PER_YEAR)
    return pd.DataFrame(
        {
            HOUR_SIN: hour_sin,
            HOUR_COS: hour_cos,
            DOW_SIN: dow_sin,
            DOW_COS: dow_cos,
            SEASON_SIN: season_sin,
            SEASON_COS: season_cos,
        },
        index=ts,
    )


def boundary_layer_proxy(timestamps: pd.DatetimeIndex) -> pd.Series:
    """A documented time-of-day/season stand-in for boundary-layer height (§5.3).

    NOT a measurement. The real mixing-layer height would come from HungaroMet; until
    that feed is confirmed this proxy encodes the well-known diurnal and seasonal
    shape — a shallow layer at night and in winter (poor dispersion, pollutants build
    up), a deep layer on summer afternoons (strong mixing, dilution). It is a unitless
    index in [0, 1] and is flagged PROXY wherever it appears.

    The shape: a diurnal cosine peaking mid-afternoon (hour 15) times a seasonal
    cosine peaking at midsummer (day-of-year 172). Both are physically-reasoned
    modelling choices, never data-derived constants.
    """
    ts = pd.DatetimeIndex(timestamps)
    hour = ts.hour.to_numpy(dtype="float64")
    doy = ts.dayofyear.to_numpy(dtype="float64")
    # Diurnal term: 0 at night, 1 mid-afternoon. cos peaks when (hour-15)=0.
    diurnal = 0.5 * (1.0 + np.cos(2.0 * np.pi * (hour - 15.0) / 24.0))
    # Seasonal term: 0 midwinter, 1 midsummer. cos peaks when (doy-172)=0.
    seasonal = 0.5 * (1.0 + np.cos(2.0 * np.pi * (doy - 172.0) / _DAYS_PER_YEAR))
    # Blend so neither term ever drives the layer fully flat; weights are a modelling
    # choice (diurnal variation dominates day to day, season modulates it).
    proxy = 0.15 + 0.85 * (0.65 * diurnal + 0.35 * seasonal)
    return pd.Series(np.clip(proxy, 0.0, 1.0), index=ts, name=BLH_PROXY)
