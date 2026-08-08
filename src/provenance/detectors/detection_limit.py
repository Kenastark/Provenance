"""R11 DETECTION_LIMIT_FLOOR: readings pinned at the instrument's detection limit.

Confirmed case: 2413 NO readings sit at exactly 0.7 µg/m3, the sensor's lower
detection limit. A value at the floor is *left-censored* - the true concentration
is "at most 0.7", not "exactly 0.7" - so treating it as a measurement biases any
downstream statistic. A run of such values this long is flagged so the reading is
carried as censored, not real.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from provenance.detectors import _runs
from provenance.detectors.base import AuditContext, defect_frame, make_row
from provenance.schema import canonical as C

_FLOOR_ATOL = 1e-9


class DetectionLimitDetector:
    code = "R11"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        cfg = ctx.thresholds["detection_limit"]
        min_hours = int(cfg["min_consecutive_hours"])
        params = cfg.get("parameters", {})
        rows: list[dict[str, Any]] = []
        for parameter, spec in params.items():
            limit = float(spec["limit"])
            g = frame[frame[C.PARAMETER] == parameter]
            if g.empty:
                continue
            for station, sg in g.groupby(C.STATION_ID):
                sg = sg.sort_values(C.TIMESTAMP)
                values = pd.to_numeric(sg[C.VALUE], errors="coerce").to_numpy()
                at_floor = np.isclose(values, limit, atol=_FLOOR_ATOL)
                ts = pd.to_datetime(sg[C.TIMESTAMP]).to_numpy()
                cadence = ctx.coverage.series_grids.get((str(station), str(parameter)))
                step_hours = cadence.cadence if cadence else pd.Timedelta(hours=1)
                min_steps = _steps(min_hours, step_hours)
                for start, length in _runs.equal_value_runs(at_floor.astype(float)):
                    if not at_floor[start] or length < min_steps:
                        continue
                    for k in range(start, start + length):
                        rows.append(
                            make_row(
                                self.code,
                                str(station),
                                str(parameter),
                                ts[k],
                                ctx,
                                limit=limit,
                                unit=str(spec.get("unit", "")),
                                run_length=int(length),
                            )
                        )
        return defect_frame(rows)


def _steps(hours: int, cadence: pd.Timedelta) -> int:
    seconds = cadence.total_seconds()
    return max(1, math.ceil(hours * 3600 / seconds)) if seconds > 0 else hours
