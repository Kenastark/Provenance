"""Fault episodes — collapsing per-cell defect flags into distinct faults.

A detector flags every *cell* it finds wrong. That is the right resolution for a
report ("show me each bad reading") and the wrong one for asking "how many things
are wrong with this station?". A sensor frozen for a week is **one** fault, but it
flags ~168 cells; a single impossible spike is also one fault, and flags one cell.
Summing raw flag rows therefore makes one long-running fault outweigh every other
signal by two orders of magnitude.

An **episode** is a maximal run of consecutive flagged cells carrying the same
reason code on the same (station, parameter), at that series' own cadence. It
carries both its severity and its extent (``n_cells``), so a consumer can weigh
"a fault occurred" separately from "the fault spoils everything this station
reports" — the two are genuinely different questions and the trust layer needs
both (see ``trust/components.py``).

This is the same discipline the defect rate already applies at the audit layer,
where a cell counts once however many codes fired on it: raw flag rows are a
presentation detail, not a unit of measurement.
"""

from __future__ import annotations

import pandas as pd

from provenance.detectors import _runs
from provenance.detectors.base import REASON_CODE, SEVERITY
from provenance.grid.coverage import CoverageModel
from provenance.schema import canonical as C

_HOUR = pd.Timedelta(hours=1)

EPISODE_COLUMNS: tuple[str, ...] = (
    REASON_CODE,
    C.STATION_ID,
    C.PARAMETER,
    SEVERITY,
    "start_utc",
    "end_utc",
    "n_cells",
)


def empty_episode_frame() -> pd.DataFrame:
    """A correctly-typed episode frame with no rows."""
    frame = pd.DataFrame({c: pd.Series(dtype="object") for c in EPISODE_COLUMNS})
    frame["start_utc"] = pd.Series(dtype="datetime64[ns]")
    frame["end_utc"] = pd.Series(dtype="datetime64[ns]")
    frame["n_cells"] = pd.Series(dtype="int64")
    return frame


def defect_episodes(defects: pd.DataFrame, coverage: CoverageModel) -> pd.DataFrame:
    """Collapse a DefectFrame into one row per distinct fault episode.

    Cadence comes from the coverage model, so a daily series (noise) is not split
    into one episode per day merely because its readings are 24h apart.
    """
    if defects.empty:
        return empty_episode_frame()

    rows: list[dict[str, object]] = []
    for (station, parameter, code), group in defects.groupby(
        [C.STATION_ID, C.PARAMETER, REASON_CODE], sort=True
    ):
        grid = coverage.series_grids.get((str(station), str(parameter)))
        cadence = grid.cadence if grid is not None else _HOUR
        timestamps = pd.DatetimeIndex(pd.to_datetime(group[C.TIMESTAMP]).unique())
        severity = str(group[SEVERITY].iloc[0])
        for run in _runs.consecutive_runs(timestamps, cadence):
            rows.append(
                {
                    REASON_CODE: str(code),
                    C.STATION_ID: str(station),
                    C.PARAMETER: str(parameter),
                    SEVERITY: severity,
                    "start_utc": run[0],
                    "end_utc": run[-1],
                    "n_cells": len(run),
                }
            )
    if not rows:
        return empty_episode_frame()
    frame = pd.DataFrame(rows)[list(EPISODE_COLUMNS)]
    return frame.sort_values(
        [C.STATION_ID, C.PARAMETER, REASON_CODE, "start_utc"], kind="stable"
    ).reset_index(drop=True)
