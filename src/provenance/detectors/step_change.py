"""R14 STEP_CHANGE: a sustained level shift, via a tabular CUSUM control chart.

A step change is a reading that jumps to a new level and *stays* there - a
recalibration, a sensor swap, a mounting knocked loose. Unlike a spike it does not
return, so a simple threshold misses it; a CUSUM accumulates small persistent
deviations until they are unmistakable. Parameters are the SPC standard (Montgomery):
k = 0.5 sigma, h = 5 sigma, giving an in-control ARL of ~465.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from provenance.detectors.base import AuditContext, defect_frame, make_row
from provenance.schema import canonical as C


class StepChangeDetector:
    code = "R14"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        cfg = ctx.thresholds["step_change"]
        k = float(cfg["cusum_k"])
        h = float(cfg["cusum_h"])
        min_points = int(cfg["min_points"])
        bounds = ctx.thresholds.get("physical_bounds", {})
        floors = ctx.thresholds.get("detection_limit", {}).get("parameters", {})
        rows: list[dict[str, Any]] = []
        for (station, parameter), g in frame.groupby([C.STATION_ID, C.PARAMETER]):
            g = g.sort_values(C.TIMESTAMP)
            values = pd.to_numeric(g[C.VALUE], errors="coerce").to_numpy(dtype="float64")
            ts = pd.to_datetime(g[C.TIMESTAMP]).to_numpy()
            # Physically impossible readings (R07/R08) and detection-floor values
            # (R11) are other detectors' concern; excluding them keeps a spike or a
            # censored run from masquerading as a sustained shift here.
            keep = self._in_scope(
                values, bounds.get(str(parameter), {}), floors.get(str(parameter))
            )
            values, ts = values[keep], ts[keep]
            if len(values) < min_points:
                continue
            mean = float(np.nanmean(values))
            std = float(np.nanstd(values))
            if std == 0.0 or np.isnan(std):
                continue  # a flat series is R12's job, not a step change
            z = (values - mean) / std
            unit = str(g[C.UNIT].iloc[0])
            rows.extend(self._scan(station, parameter, ts, values, z, k, h, mean, std, unit, ctx))
        return defect_frame(rows)

    @staticmethod
    def _in_scope(
        values: np.ndarray, bound: dict[str, Any], floor: dict[str, Any] | None
    ) -> np.ndarray:
        keep = ~np.isnan(values)
        lo, hi = bound.get("min"), bound.get("max")
        if lo is not None:
            keep &= values >= float(lo)
        if hi is not None:
            keep &= values <= float(hi)
        if floor is not None:
            keep &= ~np.isclose(values, float(floor["limit"]), atol=1e-9)
        return np.asarray(keep, dtype=bool)

    def _scan(
        self,
        station: object,
        parameter: object,
        ts: np.ndarray,
        values: np.ndarray,
        z: np.ndarray,
        k: float,
        h: float,
        mean: float,
        std: float,
        unit: str,
        ctx: AuditContext,
    ) -> list[dict[str, Any]]:
        # One sustained shift per series: report the first time the CUSUM crosses
        # its decision interval. Re-signalling on a wandering series would bury the
        # real recalibration events under noise, so we stop at the first crossing.
        c_pos = 0.0
        c_neg = 0.0
        for i in range(len(z)):
            if np.isnan(z[i]):
                continue
            c_pos = max(0.0, c_pos + z[i] - k)
            c_neg = max(0.0, c_neg - z[i] - k)
            if c_pos > h or c_neg > h:
                direction = "upward" if c_pos > h else "downward"
                magnitude = round(abs(float(values[i]) - mean), 4)
                return [
                    make_row(
                        self.code,
                        str(station),
                        str(parameter),
                        ts[i],
                        ctx,
                        direction=direction,
                        magnitude=magnitude,
                        unit=unit,
                        baseline_mean=round(mean, 4),
                    )
                ]
        return []
