"""Coverage detectors: R18 PARAMETER_ABSENT_STRUCTURAL and R19 SOURCE_ABSENT.

These are the guardians of standing rule 3: a sensor a station never carried is a
coverage fact, not a defect. Both codes have ``counts_toward_defect_rate = False``,
so they are reported prominently but kept out of the numerator and denominator of
the headline rate. The absences themselves are inferred by the coverage model (a
network-standard parameter entirely missing from a station); this detector just
turns them into DefectFrame rows an operator can read.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from provenance.detectors.base import AuditContext, defect_frame, make_row


class StructuralAbsenceDetector:
    """Emits both R18 and R19 from the coverage model's inferred absences."""

    code = "R18"  # nominal; rows carry their own R18/R19 per absence

    def detect(self, frame: pd.DataFrame, ctx: AuditContext) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        anchor = ctx.coverage.global_start
        for absence in ctx.coverage.structural_absences:
            rows.append(
                make_row(
                    absence.reason_code,
                    absence.station_id,
                    absence.parameter,
                    anchor,
                    ctx,
                    domain=absence.domain,
                    excluded_cells=absence.n_excluded_cells,
                    note="structural coverage fact; excluded from the defect rate",
                )
            )
        return defect_frame(rows)
