"""Timestamp-integrity detectors: R03 DUPLICATE_TIMESTAMP and R04 TIMESTAMP_OUT_OF_ORDER.

These fire on the *shape* of the index, not on values. R03 catches two different
readings claiming the same (station, parameter, hour); R04 catches a reading
stamped earlier than one already seen in file order. The canonical frame is sorted
and de-duplicated for the rest of the pipeline, so these run against the frame as
delivered.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from provenance.detectors.base import AuditContext, defect_frame, empty_defect_frame, make_row
from provenance.schema import canonical as C


class DuplicateTimestampDetector:
    code = "R03"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        keys = [C.STATION_ID, C.PARAMETER, C.TIMESTAMP]
        dup_mask = frame.duplicated(subset=keys, keep=False)
        if not dup_mask.any():
            return empty_defect_frame()
        rows: list[dict[str, Any]] = []
        for (station, parameter, ts), g in frame[dup_mask].groupby(keys):
            rows.append(
                make_row(
                    self.code,
                    str(station),
                    str(parameter),
                    ts,
                    ctx,
                    n_readings=len(g),
                    values=[None if pd.isna(v) else float(v) for v in g[C.VALUE].tolist()],
                )
            )
        return defect_frame(rows)


class OutOfOrderDetector:
    code = "R04"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for (station, parameter), g in frame.groupby([C.STATION_ID, C.PARAMETER], sort=False):
            ts: list[pd.Timestamp] = list(pd.to_datetime(g[C.TIMESTAMP]))
            running_max = ts[0]
            for i in range(1, len(ts)):
                if ts[i] < running_max:
                    rows.append(
                        make_row(
                            self.code,
                            str(station),
                            str(parameter),
                            ts[i],
                            ctx,
                            previous_max=running_max.isoformat(),
                            this_timestamp=ts[i].isoformat(),
                        )
                    )
                else:
                    running_max = ts[i]
        return defect_frame(rows)
