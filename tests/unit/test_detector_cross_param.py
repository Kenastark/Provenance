"""R09 CROSS_PARAM_INVERSION (PM2.5 > PM10)."""

from __future__ import annotations

from tests.support import series_rows

from provenance.detectors.cross_param import CrossParamInversionDetector


def _pm(pm10: list[float], pm25: list[float], make_frame):
    rows = series_rows("S1", "PM10", pm10) + series_rows("S1", "PM2.5", pm25)
    return make_frame(rows)


def test_r09_flags_inversion(make_frame, make_ctx) -> None:
    frame = _pm([20.0, 20.0, 20.0], [10.0, 25.0, 10.0], make_frame)  # hour 1 inverted
    out = CrossParamInversionDetector().detect(frame, make_ctx(frame))
    assert list(out["reason_code"]) == ["R09"]
    ev = out.iloc[0]["evidence"]
    assert ev["pm25"] == 25.0 and ev["pm10"] == 20.0


def test_r09_negative_when_ordering_holds(make_frame, make_ctx) -> None:
    frame = _pm([20.0, 30.0, 40.0], [10.0, 15.0, 20.0], make_frame)
    assert CrossParamInversionDetector().detect(frame, make_ctx(frame)).empty


def test_r09_boundary_equal_not_flagged(make_frame, make_ctx) -> None:
    frame = _pm([20.0, 20.0], [20.0, 20.0], make_frame)  # equal is physically allowed
    assert CrossParamInversionDetector().detect(frame, make_ctx(frame)).empty
