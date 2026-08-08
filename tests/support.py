"""Importable test helpers (kept out of conftest so tests can import them directly).

conftest.py is loaded by pytest as a plugin, not as an importable module; shared
constructors that tests call at call-sites live here instead.
"""

from __future__ import annotations

import pandas as pd

from provenance.schema import canonical as C


def series_rows(
    station: str,
    parameter: str,
    values: list[float],
    *,
    unit: str = "µg/m3",
    start: str = "2026-05-01T00:00:00",
    freq: str = "h",
    source: str = "test_air.csv",
) -> list[dict]:
    """Expand a value list into canonical row dicts at a fixed cadence."""
    times = pd.date_range(start=start, periods=len(values), freq=freq)
    return [
        {
            C.STATION_ID: station,
            C.PARAMETER: parameter,
            C.TIMESTAMP: ts,
            C.VALUE: float(v),
            C.UNIT: unit,
            C.SOURCE_FILE: source,
        }
        for ts, v in zip(times, values, strict=True)
    ]
