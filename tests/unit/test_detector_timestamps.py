"""R03 DUPLICATE_TIMESTAMP and R04 TIMESTAMP_OUT_OF_ORDER."""

from __future__ import annotations

import pandas as pd
from tests.support import series_rows

from provenance.config.loading import load_thresholds
from provenance.detectors.base import AuditContext
from provenance.detectors.timestamps import DuplicateTimestampDetector, OutOfOrderDetector
from provenance.grid.coverage import build_coverage
from provenance.schema import canonical as C


def test_r03_flags_duplicate_cell(make_frame, make_ctx) -> None:
    rows = series_rows("S1", "PM10", [10.0, 11.0, 12.0])
    rows.append({**rows[1], C.VALUE: 99.0})  # duplicate (station, param, ts), different value
    frame = make_frame(rows)
    out = DuplicateTimestampDetector().detect(frame, make_ctx(frame))
    assert list(out["reason_code"]) == ["R03"]
    assert out.iloc[0]["evidence"]["n_readings"] == 2


def test_r03_negative_when_unique(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "PM10", [10.0, 11.0, 12.0]))
    assert DuplicateTimestampDetector().detect(frame, make_ctx(frame)).empty


def test_r03_boundary_three_way_duplicate(make_frame, make_ctx) -> None:
    rows = series_rows("S1", "PM10", [10.0, 11.0])
    rows.append({**rows[0], C.VALUE: 20.0})
    rows.append({**rows[0], C.VALUE: 30.0})
    frame = make_frame(rows)
    out = DuplicateTimestampDetector().detect(frame, make_ctx(frame))
    assert out.iloc[0]["evidence"]["n_readings"] == 3


def _raw(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.SOURCE_FILE] = "test_air.csv"
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    return C.add_row_hash(frame)  # deliberately NOT validated/sorted


def test_r04_flags_out_of_order_row() -> None:
    rows = series_rows("S1", "PM10", [10.0, 11.0, 12.0, 13.0])
    rows[2], rows[3] = rows[3], rows[2]  # swap so row 3 is earlier than row 2
    frame = _raw(rows)
    ctx = AuditContext(thresholds=load_thresholds(), coverage=build_coverage(C.validate(frame)))
    out = OutOfOrderDetector().detect(frame, ctx)
    assert list(out["reason_code"]) == ["R04"]


def test_r04_negative_on_sorted_frame(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "PM10", [10.0, 11.0, 12.0, 13.0]))
    assert OutOfOrderDetector().detect(frame, make_ctx(frame)).empty
