"""Assemble the feature matrix for a readings frame, with honest provenance.

The output is a matrix indexed by ``(station_id, timestamp_utc)`` — one row per
station-hour — carrying meteorology, the boundary-layer proxy, calendar features and
a traffic covariate, plus a :class:`FeatureSet` recording where each column came
from. The deweather model joins a pollutant's values onto this by index to get its
training target; the residual it leaves behind is what anomaly detection sees.

Meteorology splits by what the network actually measures:

* ``Wind_Speed``/``Wind_Direction``/``Humidity``/``Pressure`` are confirmed export
  parameters, read from the readings frame itself and flagged MEASURED. A station
  that did not report a given hour is imputed from the city-wide hourly mean (wind
  direction circularly, via its sin/cos), then the global mean — the same
  city-fallback idea the wind graph uses, never a fabricated calm.
* ``temperature``/``precipitation`` are HungaroMet fields the export does not carry.
  When a confirmed weather frame is passed they are joined on the hour and flagged
  WEATHER_FEED; when it is absent they are imputed constants flagged unavailable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from provenance.models.features.calendar import (
    BLH_PROXY,
    boundary_layer_proxy,
    calendar_features,
)
from provenance.models.features.provenance import (
    FeatureProvenance,
    FeatureSet,
    FeatureSpec,
)
from provenance.models.features.traffic import TRAFFIC_FLOW, traffic_feature
from provenance.models.features.wind import (
    WIND_COS,
    WIND_DEGREES,
    WIND_SIN,
    encode_wind_direction,
)
from provenance.schema import canonical as C

# Confirmed in-situ meteorology parameters (schema_assumptions.yaml: known_parameters).
WIND_SPEED_PARAM = "Wind_Speed"
WIND_DIR_PARAM = "Wind_Direction"
HUMIDITY_PARAM = "Humidity"
PRESSURE_PARAM = "Pressure"

WIND_SPEED = "wind_speed"
HUMIDITY = "humidity"
PRESSURE = "pressure"
TEMPERATURE = "temperature"
PRECIPITATION = "precipitation"

# HungaroMet weather-frame column names (the covariate feed, when confirmed).
WEATHER_TEMPERATURE = "temperature"
WEATHER_PRECIPITATION = "precipitation"

_IMPUTED_TEMPERATURE = 10.0  # °C: a mild placeholder, only used flagged-unavailable.
_IMPUTED_PRECIPITATION = 0.0  # mm.


def build_features(
    frame: pd.DataFrame,
    *,
    weather: pd.DataFrame | None = None,
    per_interval_traffic: pd.Series | None = None,
    wind_encoding: str = "sincos",
) -> tuple[pd.DataFrame, FeatureSet]:
    """Build the ``(station, hour)`` feature matrix and its provenance contract.

    ``wind_encoding`` is ``"sincos"`` (the honest circular encoding) or ``"degrees"``
    (raw bearing) — the second exists only so the test gate can prove the first is
    better; production always uses ``"sincos"``.
    """
    if wind_encoding not in {"sincos", "degrees"}:
        raise ValueError(f"wind_encoding must be 'sincos' or 'degrees', not {wind_encoding!r}")

    stations = sorted(frame[C.STATION_ID].astype(str).unique())
    times = pd.DatetimeIndex(sorted(frame[C.TIMESTAMP].unique()))
    index = pd.MultiIndex.from_product([stations, times], names=[C.STATION_ID, C.TIMESTAMP])

    met = _meteorology(frame, stations, times)  # indexed by the same MultiIndex

    cols: dict[str, np.ndarray] = {}
    specs: list[FeatureSpec] = []

    # --- HungaroMet weather feed (temperature, precipitation) -----------------
    temp, precip, weather_available = _weather_feed(weather, times, stations, index)
    cols[TEMPERATURE] = temp
    cols[PRECIPITATION] = precip
    specs.append(
        FeatureSpec(
            TEMPERATURE,
            FeatureProvenance.WEATHER_FEED,
            "Air temperature from HungaroMet."
            + ("" if weather_available else " Feed unconfirmed; imputed constant (§5.3)."),
            available=weather_available,
        )
    )
    specs.append(
        FeatureSpec(
            PRECIPITATION,
            FeatureProvenance.WEATHER_FEED,
            "Precipitation from HungaroMet."
            + ("" if weather_available else " Feed unconfirmed; imputed constant (§5.3)."),
            available=weather_available,
        )
    )

    # --- In-situ meteorology (measured by the network) ------------------------
    cols[WIND_SPEED] = met[WIND_SPEED].to_numpy()
    specs.append(FeatureSpec(WIND_SPEED, FeatureProvenance.MEASURED, "In-situ wind speed."))
    if wind_encoding == "sincos":
        cols[WIND_SIN] = met[WIND_SIN].to_numpy()
        cols[WIND_COS] = met[WIND_COS].to_numpy()
        specs.append(
            FeatureSpec(WIND_SIN, FeatureProvenance.MEASURED, "sin of wind bearing (circular).")
        )
        specs.append(
            FeatureSpec(WIND_COS, FeatureProvenance.MEASURED, "cos of wind bearing (circular).")
        )
    else:
        cols[WIND_DEGREES] = met[WIND_DEGREES].to_numpy()
        specs.append(
            FeatureSpec(
                WIND_DEGREES,
                FeatureProvenance.MEASURED,
                "Raw wind bearing in degrees (test-only; breaks the 359°/1° adjacency).",
            )
        )
    cols[HUMIDITY] = met[HUMIDITY].to_numpy()
    specs.append(FeatureSpec(HUMIDITY, FeatureProvenance.MEASURED, "In-situ relative humidity."))
    cols[PRESSURE] = met[PRESSURE].to_numpy()
    specs.append(FeatureSpec(PRESSURE, FeatureProvenance.MEASURED, "In-situ barometric pressure."))

    # --- Boundary-layer proxy (documented stand-in) ---------------------------
    blh = boundary_layer_proxy(times)
    cols[BLH_PROXY] = _broadcast_over_stations(blh, stations)
    specs.append(
        FeatureSpec(
            BLH_PROXY,
            FeatureProvenance.PROXY,
            "Boundary-layer height proxy: a documented time-of-day/season index, not "
            "the measured mixing height (§5.3).",
        )
    )

    # --- Calendar (derived from the timestamp) --------------------------------
    cal = calendar_features(times)
    for name in cal.columns:
        cols[name] = _broadcast_over_stations(cal[name], stations)
        specs.append(FeatureSpec(name, FeatureProvenance.DERIVED, "Calendar cycle (sin/cos)."))

    # --- Traffic covariate (repaired Enclod counters) -------------------------
    traffic, traffic_available = traffic_feature(times, per_interval_traffic)
    cols[TRAFFIC_FLOW] = _broadcast_over_stations(traffic, stations)
    specs.append(
        FeatureSpec(
            TRAFFIC_FLOW,
            FeatureProvenance.TRAFFIC,
            "Hourly vehicle throughput from repaired Enclod counters."
            + ("" if traffic_available else " Feed unconfirmed; imputed constant (ADR 0003)."),
            available=traffic_available,
        )
    )

    matrix = pd.DataFrame(cols, index=index)
    return matrix, FeatureSet(tuple(specs))


def _broadcast_over_stations(per_hour: pd.Series, stations: list[str]) -> np.ndarray:
    """Tile a per-hour series across stations to match the (station, hour) index order."""
    return np.tile(per_hour.to_numpy(dtype="float64"), len(stations))


def _meteorology(frame: pd.DataFrame, stations: list[str], times: pd.DatetimeIndex) -> pd.DataFrame:
    """A dense (station, hour) meteorology table, imputed from city means where absent.

    Wind direction is imputed circularly: its sin and cos are averaged as unit-vector
    components (never the raw bearing), so a missing 350°/10° pair fills toward north,
    not toward south.
    """
    index = pd.MultiIndex.from_product([stations, times], names=[C.STATION_ID, C.TIMESTAMP])
    out = pd.DataFrame(index=index)

    for param, name in (
        (WIND_SPEED_PARAM, WIND_SPEED),
        (HUMIDITY_PARAM, HUMIDITY),
        (PRESSURE_PARAM, PRESSURE),
    ):
        out[name] = _dense_param(frame, param, stations, times)

    # Wind direction → sin/cos, then impute the components (circular-correct).
    dir_dense = _dense_param(frame, WIND_DIR_PARAM, stations, times, impute=False)
    sincos = encode_wind_direction(dir_dense.reset_index(drop=True))
    sincos.index = dir_dense.index
    for comp in (WIND_SIN, WIND_COS):
        out[comp] = _impute_hourly(sincos[comp])
    # A raw-degrees column too, for the wind-encoding test; imputed toward 0° when absent.
    out[WIND_DEGREES] = _impute_hourly(dir_dense).fillna(0.0)
    return out


def _dense_param(
    frame: pd.DataFrame,
    parameter: str,
    stations: list[str],
    times: pd.DatetimeIndex,
    *,
    impute: bool = True,
) -> pd.Series:
    """Reindex one parameter onto the full (station, hour) grid; optionally impute."""
    index = pd.MultiIndex.from_product([stations, times], names=[C.STATION_ID, C.TIMESTAMP])
    rows = frame[frame[C.PARAMETER] == parameter]
    if rows.empty:
        series = pd.Series(np.nan, index=index, name=parameter)
    else:
        pivot = rows.groupby([C.STATION_ID, C.TIMESTAMP])[C.VALUE].mean().astype("float64")
        series = pivot.reindex(index)
    return _impute_hourly(series) if impute else series


def _impute_hourly(series: pd.Series) -> pd.Series:
    """Fill NaNs with the city-wide mean for that hour, then the global mean, then 0."""
    filled = series.copy()
    if filled.notna().any():
        hourly_mean = filled.groupby(level=C.TIMESTAMP).transform("mean")
        filled = filled.fillna(hourly_mean)
        filled = filled.fillna(float(filled.mean()))
    return filled.fillna(0.0)


def _weather_feed(
    weather: pd.DataFrame | None,
    times: pd.DatetimeIndex,
    stations: list[str],
    index: pd.MultiIndex,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Join the HungaroMet weather frame on the hour, or impute a flagged placeholder."""
    if weather is None or weather.empty:
        n = len(index)
        return (
            np.full(n, _IMPUTED_TEMPERATURE),
            np.full(n, _IMPUTED_PRECIPITATION),
            False,
        )
    w = weather.copy()
    w[C.TIMESTAMP] = pd.to_datetime(w[C.TIMESTAMP])
    w = w.set_index(C.TIMESTAMP)
    temp = w[WEATHER_TEMPERATURE].reindex(times).astype("float64")
    temp = temp.ffill().bfill().fillna(_IMPUTED_TEMPERATURE)
    precip = w[WEATHER_PRECIPITATION].reindex(times).astype("float64")
    precip = precip.fillna(_IMPUTED_PRECIPITATION)
    return (
        _broadcast_over_stations(temp, stations),
        _broadcast_over_stations(precip, stations),
        True,
    )
