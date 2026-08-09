"""Deterministic synthetic scenarios for the propagation adjudicator.

The default fixture corpus carries no wind and no propagating plume, so it cannot
exercise the adjudicator. These builders make small, fully-deterministic canonical
frames that do — a source station with a spike, downwind neighbours on a line, and a
constant wind that carries the plume toward them — parameterised only by *which*
neighbours actually rise. The verdict is never encoded here: a scenario is data, and
the tests assert what the adjudicator makes of it (standing rule: no outcome is
hinted at in the code).

They stand in, in CI, for the real KER11 centrepiece the demo adjudicates live: the
real ~4,100 µg/m³ event is in the un-committed Green Sentinel export (standing rule
7), so the characterization test freezes a scenario built here instead — a
KER11-shaped corroborated plume — and the replay CLI adjudicates the true event when
pointed at a real drop.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from provenance.config.loading import load_graph_config
from provenance.graph.adjudicate import CandidateEvent
from provenance.graph.edges import WindEdgeParams, distance_decay
from provenance.graph.geometry import haversine_km
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField
from provenance.schema import canonical as C

_PARAMETER = "PM10"
_UNIT = "µg/m3"
_BASELINE = 30.0
# A KER11-shaped source spike: above the 2000 µg/m³ sensor ceiling (so the audit
# flags it R07 "exceeds physical max"), which is exactly the "looks impossible, is it
# real?" case the adjudicator exists to settle. The attenuated downwind rises stay
# comfortably under the ceiling, so only the source reads as physically impossible.
_EVENT_VALUE = 3000.0
_WIND_FROM_DEG = 270.0  # a westerly: air travels due east, toward the neighbour line
_WIND_SPEED = 5.0
_WIND_SPEED_UNIT = "m/s"

# A source in the west and neighbours stepping due east, so bearing source→neighbour
# (~90°) aligns with the direction the westerly carries the plume. The upwind control
# sits to the west and must never read as downwind.
_SOURCE = StationPoint("SCEN-SRC", 47.530000, 21.550000)
_DOWNWIND = [
    StationPoint("SCEN-N1", 47.530000, 21.590000),  # ~3 km east
    StationPoint("SCEN-N2", 47.530000, 21.630000),  # ~6 km east
]
_UPWIND = StationPoint("SCEN-UP", 47.530000, 21.510000)  # ~3 km west (control)

_START = pd.Timestamp("2026-06-01T00:00:00")
_HOURS = 72
_EVENT_HOUR = 60


@dataclass(frozen=True, slots=True)
class Scenario:
    """A built scenario: the readings, the graph geometry, the wind, and the event."""

    name: str
    frame: pd.DataFrame
    points: list[StationPoint]
    wind: WindField
    event: CandidateEvent


def _times() -> pd.DatetimeIndex:
    return pd.DatetimeIndex([_START + pd.Timedelta(hours=h) for h in range(_HOURS)])


def _rows_for_station(
    station: StationPoint, times: pd.DatetimeIndex, values: np.ndarray
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ts, val in zip(times, values.tolist(), strict=True):
        rows.append(
            {
                C.STATION_ID: station.station_id,
                C.PARAMETER: _PARAMETER,
                C.TIMESTAMP: ts,
                C.VALUE: round(float(val), 4),
                C.UNIT: _UNIT,
                C.SOURCE_FILE: f"{station.station_id}_air.csv",
            }
        )
        rows.append(
            {
                C.STATION_ID: station.station_id,
                C.PARAMETER: "Wind_Direction",
                C.TIMESTAMP: ts,
                C.VALUE: _WIND_FROM_DEG,
                C.UNIT: "degrees",
                C.SOURCE_FILE: f"{station.station_id}_air.csv",
            }
        )
        rows.append(
            {
                C.STATION_ID: station.station_id,
                C.PARAMETER: "Wind_Speed",
                C.TIMESTAMP: ts,
                C.VALUE: _WIND_SPEED,
                C.UNIT: _WIND_SPEED_UNIT,
                C.SOURCE_FILE: f"{station.station_id}_air.csv",
            }
        )
    return rows


def build_scenario(name: str, rises: list[bool]) -> Scenario:
    """Build a scenario where downwind neighbour *k* rises iff ``rises[k]``.

    A rising neighbour is set, at the evaluation hour (event + 1h), to exactly the
    attenuated excess a genuine plume would deliver — so it corroborates. A
    non-rising neighbour stays at baseline. The upwind control never rises.
    """
    if len(rises) != len(_DOWNWIND):
        raise ValueError(f"expected {len(_DOWNWIND)} rise flags, got {len(rises)}")
    cfg = load_graph_config()
    wind_params = WindEdgeParams.from_config(cfg)
    times = _times()
    event_excess = _EVENT_VALUE - _BASELINE

    rows: list[dict[str, object]] = []

    # Source: flat baseline, one spike at the event hour.
    src_values = np.full(_HOURS, _BASELINE)
    src_values[_EVENT_HOUR] = _EVENT_VALUE
    rows += _rows_for_station(_SOURCE, times, src_values)

    # Downwind neighbours: rise (to the expected attenuated level) at event + 1h if flagged.
    for neighbour, rise in zip(_DOWNWIND, rises, strict=True):
        values = np.full(_HOURS, _BASELINE)
        if rise:
            dist = haversine_km(_SOURCE.lat, _SOURCE.lon, neighbour.lat, neighbour.lon)
            expected_excess = event_excess * distance_decay(dist, wind_params)
            values[_EVENT_HOUR + 1] = _BASELINE + expected_excess
        rows += _rows_for_station(neighbour, times, values)

    # Upwind control: always flat. It must fall below the downwind weight floor.
    rows += _rows_for_station(_UPWIND, times, np.full(_HOURS, _BASELINE))

    frame = _materialise(rows)
    points = [_SOURCE, *_DOWNWIND, _UPWIND]
    wind = WindField.from_frame(frame)
    event = CandidateEvent(
        station_id=_SOURCE.station_id,
        parameter=_PARAMETER,
        timestamp=times[_EVENT_HOUR],
        value=_EVENT_VALUE,
        baseline=_BASELINE,
        anomaly_score=1.0,
        unit=_UNIT,
    )
    return Scenario(name=name, frame=frame, points=points, wind=wind, event=event)


def _materialise(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    frame = C.add_row_hash(frame)
    return C.validate(frame)


def corroborated_plume() -> Scenario:
    """Both downwind neighbours show the expected delayed, attenuated rise → genuine."""
    return build_scenario("corroborated_plume", [True, True])


def isolated_fault() -> Scenario:
    """The source spikes alone; downwind neighbours stay flat → an isolated fault."""
    return build_scenario("isolated_fault", [False, False])


def partial_ambiguous() -> Scenario:
    """Only the farther neighbour rises: partial, edge-weighted corroboration → ambiguous."""
    return build_scenario("partial_ambiguous", [False, True])
