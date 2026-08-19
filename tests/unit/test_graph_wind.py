"""The wind field: circular means, station-local reads, and the city-level fallback."""

from __future__ import annotations

import pandas as pd
import pytest

from provenance.graph.wind import WindField, WindProvenance
from provenance.schema import canonical as C


def _wind_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    if C.SOURCE_FILE not in frame.columns:
        frame[C.SOURCE_FILE] = "air.csv"
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    frame = C.add_row_hash(frame)
    return C.validate(frame)


def _dir_speed(station: str, ts: str, direction: float, speed: float) -> list[dict]:
    return [
        {
            C.STATION_ID: station,
            C.PARAMETER: "Wind_Direction",
            C.TIMESTAMP: ts,
            C.VALUE: direction,
            C.UNIT: "degrees",
        },
        {
            C.STATION_ID: station,
            C.PARAMETER: "Wind_Speed",
            C.TIMESTAMP: ts,
            C.VALUE: speed,
            C.UNIT: "m/s",
        },
    ]


def test_empty_frame_has_no_wind() -> None:
    field = WindField.from_frame(
        pd.DataFrame(columns=[C.STATION_ID, C.PARAMETER, C.TIMESTAMP, C.VALUE, C.UNIT])
    )
    assert field.has_wind is False
    assert field.at(pd.Timestamp("2026-06-01T00:00:00"), "STA-01") is None


def test_station_local_read_is_used() -> None:
    frame = _wind_frame(_dir_speed("STA-01", "2026-06-01T00:00:00", 90.0, 4.0))
    field = WindField.from_frame(frame)
    vec = field.at(pd.Timestamp("2026-06-01T00:00:00"), "STA-01")
    assert vec is not None
    assert vec.provenance is WindProvenance.STATION_LOCAL
    assert vec.from_deg == pytest.approx(90.0)
    assert vec.speed == pytest.approx(4.0)
    assert vec.station_count == 1


def test_missing_station_falls_back_to_city() -> None:
    # STA-01 reports; STA-02 (a KER15 analogue) carries no wind sensor and falls back.
    frame = _wind_frame(_dir_speed("STA-01", "2026-06-01T00:00:00", 90.0, 4.0))
    field = WindField.from_frame(frame)
    vec = field.at(pd.Timestamp("2026-06-01T00:00:00"), "STA-02")
    assert vec is not None
    assert vec.provenance is WindProvenance.CITY_FALLBACK


def test_city_mean_is_circular_not_arithmetic() -> None:
    # 350° and 10° average to 0°, not 180°.
    rows = _dir_speed("A", "2026-06-01T00:00:00", 350.0, 3.0) + _dir_speed(
        "B", "2026-06-01T00:00:00", 10.0, 5.0
    )
    field = WindField.from_frame(_wind_frame(rows))
    city = field.city_at(pd.Timestamp("2026-06-01T00:00:00"))
    assert city is not None
    diff = min(abs(city.from_deg), abs(city.from_deg - 360.0))
    assert diff < 1.0  # ~0°, never ~180°
    assert city.speed == pytest.approx(4.0)  # plain mean of speeds
    assert city.station_count == 2


def test_hour_with_no_wind_returns_none() -> None:
    frame = _wind_frame(_dir_speed("STA-01", "2026-06-01T00:00:00", 90.0, 4.0))
    field = WindField.from_frame(frame)
    assert field.at(pd.Timestamp("2026-06-02T00:00:00"), "STA-01") is None
