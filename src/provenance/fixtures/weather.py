"""A weather-coupled synthetic corpus for the deweathering and fault models.

This is a deliberate second fixture, separate from the golden corpus in
``generator.py``. The golden corpus is pinned by the recovery ledger and must not
move; this one exists so the model layer has a network whose pollutants genuinely
respond to weather, which is the only way the deweathering R² band and the fault
recall floors mean anything.

What it produces, all seeded and deterministic:

* a canonical **readings frame** with four weather-responsive pollutants (PM10,
  NO2, O3, CO) and the four in-situ meteorology parameters the export confirms
  (Wind_Speed, Wind_Direction, Humidity, Pressure);
* a city-level **weather frame** standing in for the HungaroMet feed (temperature,
  precipitation), joined to the readings on the hour by the feature builder.

The coupling is calibrated so weather explains a *moderate* share of each
pollutant's variance - enough that a deweather regressor lands inside the
0.15-0.90 sanity band, with real unexplained signal (genuine events + noise) left
in the residual for anomaly detection to find.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from provenance.fixtures.generator import _quantise, station_ids
from provenance.models.features.calendar import boundary_layer_proxy
from provenance.schema import canonical as C

_HOUR = pd.Timedelta(hours=1)
_START = pd.Timestamp("2026-05-01T00:00:00")


@dataclass(frozen=True, slots=True)
class _PollutantSpec:
    """A pollutant and how strongly each weather driver moves it.

    Coefficients are modelling choices (dispersion physics: wind and a deep mixing
    layer dilute; a warm sunny afternoon builds ozone), not data-derived constants.
    ``noise_ratio`` sets the share of variance left unexplained, which is what keeps
    the recoverable R² below 0.90.
    """

    name: str
    unit: str
    base: float
    k_wind: float  # dilution by wind speed (negative effect on concentration)
    k_blh: float  # dilution by boundary-layer depth
    k_temp: float  # temperature effect (photochemistry for O3; +/- per species)
    k_humid: float
    noise_ratio: float


_POLLUTANTS: tuple[_PollutantSpec, ...] = (
    _PollutantSpec(
        "PM10",
        "µg/m3",
        base=42.0,
        k_wind=-1.1,
        k_blh=-22.0,
        k_temp=0.20,
        k_humid=0.10,
        noise_ratio=0.45,
    ),
    _PollutantSpec(
        "NO2",
        "µg/m3",
        base=38.0,
        k_wind=-1.0,
        k_blh=-16.0,
        k_temp=-0.35,
        k_humid=0.05,
        noise_ratio=0.45,
    ),
    _PollutantSpec(
        "O3",
        "µg/m3",
        base=55.0,
        k_wind=0.4,
        k_blh=10.0,
        k_temp=1.6,
        k_humid=-0.25,
        noise_ratio=0.40,
    ),
    _PollutantSpec(
        "CO",
        "µg/m3",
        base=400.0,
        k_wind=-8.0,
        k_blh=-120.0,
        k_temp=-1.5,
        k_humid=0.8,
        noise_ratio=0.50,
    ),
)

_METEO_UNITS = {
    "Wind_Speed": "km/h",
    "Wind_Direction": "degrees",
    "Humidity": "percent",
    "Pressure": "mbar",
}

# Genuine, weather-unexplained excursions: (station_index, pollutant, hour, magnitude).
# These are real events, not faults — they leave a residual the deweather model
# cannot explain, which is exactly what downstream anomaly detection should keep.
_GENUINE_EVENTS = (
    (0, "PM10", 240, 120.0),
    (1, "NO2", 360, 80.0),
    (2, "O3", 480, 90.0),
)


def generate_weather_corpus(
    *,
    seed: int = 20260907,
    n_days: int = 30,
    n_stations: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(readings_frame, weather_frame)`` — canonical readings plus city weather.

    Deterministic in ``seed``: two calls with the same arguments produce identical
    frames, which is what lets the SHAP-stability and recall tests compare runs.
    """
    rng = np.random.RandomState(seed)
    stations = station_ids(n_stations)
    hours = n_days * 24
    t = np.arange(hours, dtype="float64")
    times = pd.DatetimeIndex([_START + i * _HOUR for i in range(hours)])

    # --- City-level weather (the HungaroMet stand-in) -------------------------
    day_frac = (t % 24) / 24.0
    season = np.sin(2 * np.pi * t / (365.25 * 24))  # slow annual drift over the window
    diurnal = np.cos(2 * np.pi * (day_frac - 15.0 / 24.0))  # peaks mid-afternoon
    temperature = 18.0 + 6.0 * season + 6.0 * diurnal + rng.normal(0, 1.2, hours)
    precipitation = np.clip(rng.gamma(0.2, 2.0, hours) - 0.3, 0.0, None)
    blh = boundary_layer_proxy(times).to_numpy()

    weather = pd.DataFrame(
        {
            C.TIMESTAMP: times,
            "temperature": np.round(temperature, 4),
            "precipitation": np.round(precipitation, 4),
        }
    )

    rows: list[dict[str, object]] = []
    for s_ix, station in enumerate(stations):
        src_air = f"{station}_air.csv"
        # Per-station in-situ meteorology, varying slightly around the city field.
        wind_speed = np.clip(
            8.0
            + 4.0 * np.cos(2 * np.pi * (day_frac - 0.6))
            + rng.normal(0, 1.5, hours)
            + s_ix * 0.3,
            0.2,
            None,
        )
        wind_dir = (
            200.0 + 40.0 * np.sin(2 * np.pi * t / 72.0) + rng.normal(0, 15, hours) + s_ix * 5
        ) % 360.0
        humidity = np.clip(85.0 - 1.6 * temperature + rng.normal(0, 4, hours), 20.0, 100.0)
        pressure = 1013.0 + 6.0 * np.sin(2 * np.pi * t / 120.0) + rng.normal(0, 2.5, hours)

        _append_meteo(rows, station, times, "Wind_Speed", wind_speed, src_air)
        _append_meteo(rows, station, times, "Wind_Direction", wind_dir, src_air)
        _append_meteo(rows, station, times, "Humidity", humidity, src_air)
        _append_meteo(rows, station, times, "Pressure", pressure, src_air)

        for spec in _POLLUTANTS:
            signal = (
                spec.base
                + spec.k_wind * (wind_speed - wind_speed.mean())
                + spec.k_blh * (blh - blh.mean())
                + spec.k_temp * (temperature - temperature.mean())
                + spec.k_humid * (humidity - humidity.mean())
            )
            # Scale noise to the requested unexplained share of the signal's variance.
            signal_std = float(signal.std()) or 1.0
            noise_std = signal_std * np.sqrt(spec.noise_ratio / max(1e-6, 1.0 - spec.noise_ratio))
            values = signal + rng.normal(0, noise_std, hours)
            for s2_ix, pol, hour, mag in _GENUINE_EVENTS:
                if s2_ix == s_ix and pol == spec.name and hour < hours:
                    values[hour] += mag
            values = np.clip(values, 0.0, None)
            _append_meteo(rows, station, times, spec.name, values, src_air, unit=spec.unit)

    frame = _materialise(rows)
    return frame, weather


def _append_meteo(
    rows: list[dict[str, object]],
    station: str,
    times: pd.DatetimeIndex,
    parameter: str,
    values: np.ndarray,
    source: str,
    *,
    unit: str | None = None,
) -> None:
    resolved_unit = unit if unit is not None else _METEO_UNITS[parameter]
    for ts, v in zip(times, values.tolist(), strict=True):
        rows.append(
            {
                C.STATION_ID: station,
                C.PARAMETER: parameter,
                C.TIMESTAMP: ts,
                C.VALUE: _quantise(v),
                C.UNIT: resolved_unit,
                C.SOURCE_FILE: source,
            }
        )


def _materialise(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame = C.add_row_hash(frame)
    return C.validate(frame)
