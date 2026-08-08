"""R18 PARAMETER_ABSENT_STRUCTURAL and R19 SOURCE_ABSENT (coverage facts)."""

from __future__ import annotations

from tests.support import series_rows

from provenance.detectors.structural import StructuralAbsenceDetector


def _network(make_frame):
    rows: list[dict] = []
    for st in ("A", "B", "C", "D"):
        rows += series_rows(st, "PM10", [30.0] * 24, source="net_air.csv")
    # NO carried by A, B, D -> network-standard; C lacks it (a single-parameter gap).
    for st in ("A", "B", "D"):
        rows += series_rows(st, "NO", [10.0] * 24, source="net_air.csv")
    # Groundwater (two parameters) carried by A, B, C; D lacks the whole source.
    for st in ("A", "B", "C"):
        rows += series_rows(st, "WaterTemp", [13.0] * 24, unit="celsius", source="net_water.csv")
        rows += series_rows(st, "WaterLevel", [5.0] * 24, unit="m", source="net_water.csv")
    return make_frame(rows)


def test_r18_for_single_missing_parameter(make_frame, make_ctx) -> None:
    frame = _network(make_frame)
    out = StructuralAbsenceDetector().detect(frame, make_ctx(frame))
    r18 = out[out["reason_code"] == "R18"]
    assert list(r18["station_id"]) == ["C"]
    assert list(r18["parameter"]) == ["NO"]


def test_r19_for_whole_missing_source(make_frame, make_ctx) -> None:
    frame = _network(make_frame)
    out = StructuralAbsenceDetector().detect(frame, make_ctx(frame))
    r19 = out[out["reason_code"] == "R19"]
    assert set(r19["station_id"]) == {"D"}
    assert set(r19["parameter"]) == {"WaterTemp", "WaterLevel"}


def test_structural_codes_do_not_count_toward_rate() -> None:
    from provenance.config import reason_codes

    for code in ("R18", "R19"):
        assert reason_codes.get(code).counts_toward_defect_rate is False
