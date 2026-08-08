"""R09 CROSS_PARAM_INVERSION: PM2.5 exceeding PM10.

PM2.5 particles are a physical subset of PM10 particles, so PM2.5 <= PM10 must
hold at every co-located timestamp. Where it does not, one of the two channels is
wrong even though both readings are individually plausible - exactly the "present,
well-formed, and wrong" defect the product exists to catch. Confirmed in the
corpus at ~100 timestamps. The flag is attached to the PM2.5 cell that is too high.
"""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

from provenance.detectors.base import AuditContext, defect_frame, empty_defect_frame, make_row
from provenance.schema import canonical as C

_FINE = "PM2.5"
_COARSE = "PM10"


class CrossParamInversionDetector:
    code = "R09"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        cfg = ctx.thresholds["cross_parameter"]["pm25_le_pm10"]
        if not cfg.get("enabled", True):
            return empty_defect_frame()
        tolerance = float(cfg.get("tolerance", 0.0))

        pm = frame[frame[C.PARAMETER].isin([_FINE, _COARSE])]
        if pm.empty:
            return empty_defect_frame()
        wide = pm.pivot_table(
            index=[C.STATION_ID, C.TIMESTAMP], columns=C.PARAMETER, values=C.VALUE, aggfunc="first"
        )
        if _FINE not in wide.columns or _COARSE not in wide.columns:
            return empty_defect_frame()
        inverted = wide[wide[_FINE] > wide[_COARSE] + tolerance]
        rows: list[dict[str, Any]] = []
        for idx, r in inverted.iterrows():
            station, ts = cast("tuple[Any, Any]", idx)  # (station_id, timestamp) MultiIndex
            rows.append(
                make_row(
                    self.code,
                    str(station),
                    _FINE,
                    ts,
                    ctx,
                    pm25=float(r[_FINE]),
                    pm10=float(r[_COARSE]),
                    excess=round(float(r[_FINE] - r[_COARSE]), 4),
                )
            )
        return defect_frame(rows)
