"""The default detector set and the runner that applies them uniformly.

The environmental audit runs the value/shape/coverage detectors listed here. The
cumulative-counter codes R05 (reset) and R06 (non-monotonic) belong to the traffic
pipeline in ``io.counter_repair`` - they require running-total semantics the
environmental frame does not have - and are surfaced from there.
"""

from __future__ import annotations

import pandas as pd

from provenance.detectors.base import AuditContext, Detector, empty_defect_frame
from provenance.detectors.cross_param import CrossParamInversionDetector
from provenance.detectors.detection_limit import DetectionLimitDetector
from provenance.detectors.physical_bounds import BelowMinDetector, ExceedsMaxDetector
from provenance.detectors.row_absent import CommGapDetector, RowAbsentDetector
from provenance.detectors.sensor_dead import SensorDeadDetector
from provenance.detectors.step_change import StepChangeDetector
from provenance.detectors.structural import StructuralAbsenceDetector
from provenance.detectors.timestamps import DuplicateTimestampDetector, OutOfOrderDetector
from provenance.detectors.unit_consistency import UnitInconsistentDetector
from provenance.detectors.variance import LowVarianceDetector, ZeroVarianceDetector


def default_detectors() -> list[Detector]:
    """Every detector the phase-1 environmental audit runs, in report order."""
    return [
        RowAbsentDetector(),
        CommGapDetector(),
        DuplicateTimestampDetector(),
        OutOfOrderDetector(),
        ExceedsMaxDetector(),
        BelowMinDetector(),
        CrossParamInversionDetector(),
        UnitInconsistentDetector(),
        DetectionLimitDetector(),
        ZeroVarianceDetector(),
        LowVarianceDetector(),
        StepChangeDetector(),
        SensorDeadDetector(),
        StructuralAbsenceDetector(),
    ]


def run_detectors(
    frame: pd.DataFrame, ctx: AuditContext, detectors: list[Detector] | None = None
) -> pd.DataFrame:
    """Run every detector and concatenate their DefectFrames deterministically."""
    detectors = detectors if detectors is not None else default_detectors()
    parts = [d.detect(frame, ctx) for d in detectors]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return empty_defect_frame()
    combined = pd.concat(parts, ignore_index=True)
    from provenance.detectors.base import REASON_CODE
    from provenance.schema import canonical as C

    combined = combined.sort_values(
        [C.STATION_ID, C.PARAMETER, C.TIMESTAMP, REASON_CODE], kind="stable"
    ).reset_index(drop=True)
    return combined
