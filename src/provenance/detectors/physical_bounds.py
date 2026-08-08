"""Physical-plausibility detectors: R07 EXCEEDS_PHYSICAL_MAX and R08 BELOW_PHYSICAL_MIN.

Bounds are instrument-plausible ambient ceilings from ``thresholds.yaml``, each
with a cited basis, so a genuine impossibility (the 4100 µg/m3 PM10 spike at
KER11) trips while a bad-air-day does not. A parameter whose declared unit is
itself wrong (CO2) is bounded in its *inferred* unit, so the unit error surfaces
as R10 rather than a spurious R07.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from provenance.detectors.base import AuditContext, defect_frame, make_row
from provenance.schema import canonical as C


class _BoundsBase:
    code = ""
    _side = ""  # "max" or "min"

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        bounds = ctx.thresholds["physical_bounds"]
        rows: list[dict[str, Any]] = []
        for parameter, spec in bounds.items():
            limit = spec.get(self._side)
            if limit is None:
                continue
            g = frame[frame[C.PARAMETER] == parameter]
            if g.empty:
                continue
            values = pd.to_numeric(g[C.VALUE], errors="coerce")
            mask = values > limit if self._side == "max" else values < limit
            for idx in g.index[mask.fillna(False)]:
                row = g.loc[idx]
                rows.append(
                    make_row(
                        self.code,
                        str(row[C.STATION_ID]),
                        str(parameter),
                        row[C.TIMESTAMP],
                        ctx,
                        value=float(row[C.VALUE]),
                        limit=float(limit),
                        unit=str(row[C.UNIT]),
                        basis=str(spec.get("basis", "")),
                    )
                )
        return defect_frame(rows)


class ExceedsMaxDetector(_BoundsBase):
    code = "R07"
    _side = "max"


class BelowMinDetector(_BoundsBase):
    code = "R08"
    _side = "min"
