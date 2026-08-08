"""R21 SENSOR_DEAD: a covered series that stopped reporting and never resumed.

Distinct from a communication gap (R02), which recovers, and from structural
absence (R18/R19), where the sensor never existed: a dead sensor produced data,
then went silent for the rest of the window. In the traffic bundle this is a
cumulative counter that never advances again; here, in the environmental frame, it
is a series whose last reading precedes the end of the window by a long stretch.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from provenance.detectors.base import AuditContext, defect_frame, make_row


class SensorDeadDetector:
    code = "R21"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        cfg = ctx.thresholds["sensor_dead"]
        trailing_hours = int(cfg.get("trailing_absent_hours", 72))
        end = ctx.coverage.global_end
        rows: list[dict[str, Any]] = []
        for grid in ctx.coverage.series_grids.values():
            silence = end - grid.end
            if silence >= pd.Timedelta(hours=trailing_hours):
                rows.append(
                    make_row(
                        self.code,
                        grid.station_id,
                        grid.parameter,
                        grid.end,
                        ctx,
                        since=pd.Timestamp(grid.end).isoformat(),
                        silent_hours=int(silence.total_seconds() // 3600),
                        window_end=pd.Timestamp(end).isoformat(),
                    )
                )
        return defect_frame(rows)
