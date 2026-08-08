"""R10 UNIT_INCONSISTENT: a declared unit the value range contradicts.

Confirmed case: CO2 is labelled µg/m3, but its values (690-1634) are three orders
of magnitude too small for that unit and sit squarely in the ppm range. The reading
is not corrected here - it is flagged, with the evidence, so a human decides. Every
cell of an affected series is flagged, because every one carries the wrong label.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from provenance.detectors.base import AuditContext, defect_frame, make_row
from provenance.schema import canonical as C


class UnitInconsistentDetector:
    code = "R10"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        rules = ctx.thresholds.get("unit_inference", {})
        rows: list[dict[str, Any]] = []
        for parameter, rule in rules.items():
            declared = rule["declared_unit"]
            inferred = rule["inferred_unit"]
            lo = float(rule["inferred_range"]["min"])
            hi = float(rule["inferred_range"]["max"])
            g = frame[frame[C.PARAMETER] == parameter]
            if g.empty:
                continue
            for station, sg in g.groupby(C.STATION_ID):
                declared_units = set(sg[C.UNIT].unique())
                if declared not in declared_units:
                    continue
                values = pd.to_numeric(sg[C.VALUE], errors="coerce").dropna()
                if values.empty:
                    continue
                median = float(values.median())
                # The whole series is mislabelled when its central value sits in
                # the inferred unit's range rather than the declared one's.
                if lo <= median <= hi:
                    for _, row in sg.iterrows():
                        rows.append(
                            make_row(
                                self.code,
                                str(station),
                                str(parameter),
                                row[C.TIMESTAMP],
                                ctx,
                                declared=declared,
                                inferred=inferred,
                                observed_median=round(median, 3),
                                basis=str(rule.get("basis", "")),
                            )
                        )
        return defect_frame(rows)
