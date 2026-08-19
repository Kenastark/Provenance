"""The wind field: what the air was doing, where, and how sure we are of it.

The wind-conditioned edge needs a (from-bearing, speed) vector for a station at a
timestamp. Two facts make that non-trivial and are handled here rather than assumed
by the edge maths:

1. **Not every station measures wind.** DEB-KER15 carries no wind sensors at all
   (confirmed in ``schema_assumptions.yaml``), and others have gaps. So a station's
   wind falls back to the **city-level vector** — the circular mean over every
   station that *did* report that hour — and the fallback is recorded as the edge's
   wind *provenance*, never silently substituted (§2 of the brief).

2. **Bearings do not average arithmetically.** 350° and 10° average to 0°, not 180°.
   Directions are averaged as unit vectors (circular mean); speeds average normally.

Wind comes from the canonical readings frame (parameters ``Wind_Direction`` /
``Wind_Speed``) when present. When a corpus carries no wind at all — the default
synthetic fixture — the field is empty and every lookup returns ``None`` (calm/
unknown), which the edge layer treats as a degenerate, finite, zero-weight graph.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from provenance.schema import canonical as C

WIND_DIRECTION_PARAMETER = "Wind_Direction"
WIND_SPEED_PARAMETER = "Wind_Speed"


class WindProvenance(StrEnum):
    """Where a wind vector came from — carried onto every wind edge."""

    STATION_LOCAL = "station-local"
    CITY_FALLBACK = "city-fallback"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class WindVector:
    """Wind at one place and time: the bearing it blows FROM, and its speed."""

    from_deg: float
    speed: float
    speed_unit: str
    provenance: WindProvenance
    station_count: int
    """How many stations the vector was averaged over (1 for a station-local read)."""


def _circular_mean_deg(degrees: np.ndarray) -> float:
    radians = np.radians(degrees.astype("float64"))
    mean = math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean()))
    return (math.degrees(mean) + 360.0) % 360.0


class WindField:
    """Wind vectors over time, per station, with a city-level fallback.

    Build with :meth:`from_frame`. Look up with :meth:`at`, which never raises: an
    absent station or hour yields the city fallback, and a total absence yields
    ``None`` — the honest "no wind data", not a fabricated calm.
    """

    def __init__(
        self,
        by_station: dict[tuple[str, pd.Timestamp], WindVector],
        city: dict[pd.Timestamp, WindVector],
        speed_unit: str,
    ) -> None:
        self._by_station = by_station
        self._city = city
        self.speed_unit = speed_unit

    @property
    def has_wind(self) -> bool:
        return bool(self._city)

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> WindField:
        """Read wind vectors out of a canonical readings frame.

        Rows for the two wind parameters are pivoted to (station, hour) → (dir, speed)
        and a city-level circular mean is precomputed per hour. Absent → empty field.
        """
        wind = frame[frame[C.PARAMETER].isin([WIND_DIRECTION_PARAMETER, WIND_SPEED_PARAMETER])]
        by_station: dict[tuple[str, pd.Timestamp], WindVector] = {}
        city: dict[pd.Timestamp, WindVector] = {}
        speed_unit = ""
        if wind.empty:
            return cls(by_station, city, speed_unit)

        units = wind.loc[wind[C.PARAMETER] == WIND_SPEED_PARAMETER, C.UNIT]
        if not units.empty:
            speed_unit = str(units.iloc[0])

        pivot = wind.pivot_table(
            index=[C.STATION_ID, C.TIMESTAMP],
            columns=C.PARAMETER,
            values=C.VALUE,
            aggfunc="mean",
        ).reset_index()

        per_hour: dict[pd.Timestamp, list[tuple[float, float]]] = {}
        for record in pivot.to_dict("records"):
            direction = record.get(WIND_DIRECTION_PARAMETER)
            speed = record.get(WIND_SPEED_PARAMETER)
            if direction is None or speed is None or pd.isna(direction) or pd.isna(speed):
                continue
            station = str(record[C.STATION_ID])
            ts = pd.Timestamp(record[C.TIMESTAMP])
            dir_deg = float(direction) % 360.0
            spd = float(speed)
            by_station[(station, ts)] = WindVector(
                from_deg=dir_deg,
                speed=spd,
                speed_unit=speed_unit,
                provenance=WindProvenance.STATION_LOCAL,
                station_count=1,
            )
            per_hour.setdefault(ts, []).append((dir_deg, spd))

        # City-level fallback: circular mean of direction, plain mean of speed, per hour.
        for ts, pairs in per_hour.items():
            dirs = np.array([d for d, _ in pairs], dtype="float64")
            speeds = np.array([s for _, s in pairs], dtype="float64")
            city[ts] = WindVector(
                from_deg=_circular_mean_deg(dirs),
                speed=float(speeds.mean()),
                speed_unit=speed_unit,
                provenance=WindProvenance.CITY_FALLBACK,
                station_count=int(dirs.size),
            )
        return cls(by_station, city, speed_unit)

    def at(self, timestamp: pd.Timestamp, station_id: str) -> WindVector | None:
        """The wind for ``station_id`` at ``timestamp``: local if measured, else city.

        Returns ``None`` only when no station reported wind that hour — the edge layer
        reads that as a degenerate, zero-weight (but finite) graph.
        """
        ts = pd.Timestamp(timestamp)
        local = self._by_station.get((station_id, ts))
        if local is not None:
            return local
        return self._city.get(ts)

    def city_at(self, timestamp: pd.Timestamp) -> WindVector | None:
        """The city-level vector for an hour, ignoring station-local reads."""
        return self._city.get(pd.Timestamp(timestamp))
