"""Variance detectors: R12 ZERO_VARIANCE (frozen) and R13 LOW_VARIANCE_DEGRADED.

A frozen sensor is the archetypal "looks fine, is broken" defect: it reports a
perfectly plausible number, forever. R12 flags a covered series whose observed
values never change at all - zero variance across the whole record - which is
exactly the "20+ series carrying a single value" pattern in this corpus.

R13 is judged *relative to peers*, not by an absolute cutoff. A parameter that is
genuinely stable everywhere (groundwater temperature barely moves) must not trip;
only a sensor abnormally flat compared with other stations measuring the same
thing is degraded. That keeps the trust layer from crying wolf on stable-by-nature
channels.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from provenance.detectors.base import AuditContext, defect_frame, make_row
from provenance.detectors.row_absent import _humanise
from provenance.schema import canonical as C


class ZeroVarianceDetector:
    code = "R12"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for (station, parameter), g in frame.groupby([C.STATION_ID, C.PARAMETER]):
            values = pd.to_numeric(g[C.VALUE], errors="coerce").dropna()
            if len(values) < 2 or values.nunique() != 1:
                continue
            grid = ctx.coverage.series_grids.get((str(station), str(parameter)))
            span = (
                (grid.end - grid.start + grid.cadence) if grid else pd.Timedelta(hours=len(values))
            )
            g = g.sort_values(C.TIMESTAMP)
            for _, row in g.iterrows():
                rows.append(
                    make_row(
                        self.code,
                        str(station),
                        str(parameter),
                        row[C.TIMESTAMP],
                        ctx,
                        duration=_humanise(span),
                        frozen_value=float(values.iloc[0]),
                        n_readings=len(values),
                    )
                )
        return defect_frame(rows)


class LowVarianceDetector:
    code = "R13"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        cfg = ctx.thresholds["low_variance"]
        fraction = float(cfg["degraded_fraction"])
        min_peers = int(cfg["min_peers"])
        rows: list[dict[str, Any]] = []
        for parameter, pg in frame.groupby(C.PARAMETER):
            per_station_std: dict[str, float] = {}
            for station, sg in pg.groupby(C.STATION_ID):
                v = pd.to_numeric(sg[C.VALUE], errors="coerce").dropna()
                per_station_std[str(station)] = float(v.std(ddof=0)) if len(v) > 1 else 0.0
            # Peer baseline: median std among sensors that are not fully frozen.
            moving = [s for s in per_station_std.values() if s > 0.0]
            if len(moving) < min_peers:
                continue
            baseline = float(np.median(moving))
            if baseline <= 0.0:
                continue
            threshold = fraction * baseline
            for station, std in per_station_std.items():
                if 0.0 < std < threshold:
                    sg = pg[pg[C.STATION_ID] == station].sort_values(C.TIMESTAMP)
                    for _, row in sg.iterrows():
                        rows.append(
                            make_row(
                                self.code,
                                str(station),
                                str(parameter),
                                row[C.TIMESTAMP],
                                ctx,
                                window="full record",
                                sensor_std=round(std, 5),
                                peer_median_std=round(baseline, 5),
                            )
                        )
        return defect_frame(rows)
