"""Missingness detectors: R01 ROW_ABSENT and R02 COMM_GAP.

Missingness in this corpus is not nulls - it is *absent rows*. A conventional
completeness check sees 100% non-null and calls the network healthy; only
reindexing each covered series against its own complete grid reveals the holes.
R01 flags every absent tick; R02 promotes a long enough run of them to a
communication failure.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from provenance.detectors import _runs
from provenance.detectors.base import AuditContext, defect_frame, empty_defect_frame, make_row
from provenance.schema import canonical as C


class RowAbsentDetector:
    code = "R01"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        absent = ctx.coverage.absent_frame()
        if absent.empty:
            return empty_defect_frame()
        rows = [
            make_row(
                self.code,
                r[C.STATION_ID],
                r[C.PARAMETER],
                r[C.TIMESTAMP],
                ctx,
                expected_at=pd.Timestamp(r[C.TIMESTAMP]).isoformat(),
            )
            for _, r in absent.iterrows()
        ]
        return defect_frame(rows)


class CommGapDetector:
    """R02: a run of consecutive absent ticks long enough to mean an outage."""

    code = "R02"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        min_hours = int(ctx.thresholds["comm_gap"]["min_consecutive_hours"])
        rows: list[dict[str, Any]] = []
        for grid in ctx.coverage.series_grids.values():
            if not grid.absent_timestamps:
                continue
            min_steps = _steps_for_hours(min_hours, grid.cadence)
            absent_idx = pd.DatetimeIndex(grid.absent_timestamps)
            for run in _runs.consecutive_runs(absent_idx, grid.cadence):
                if len(run) >= min_steps:
                    duration = run[-1] - run[0] + grid.cadence
                    rows.append(
                        make_row(
                            self.code,
                            grid.station_id,
                            grid.parameter,
                            run[0],
                            ctx,
                            duration=_humanise(duration),
                            missing_ticks=len(run),
                            gap_start=run[0].isoformat(),
                            gap_end=run[-1].isoformat(),
                        )
                    )
        return defect_frame(rows)


def _steps_for_hours(hours: int, cadence: pd.Timedelta) -> int:
    seconds = cadence.total_seconds()
    if seconds <= 0:
        return hours
    return max(1, math.ceil(hours * 3600 / seconds))


def _humanise(td: pd.Timedelta) -> str:
    total_h = int(td.total_seconds() // 3600)
    if total_h >= 24:
        days, hours = divmod(total_h, 24)
        return f"{days}d {hours}h" if hours else f"{days}d"
    return f"{total_h}h"
