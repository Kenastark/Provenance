"""Cumulative traffic-counter repair: R05, R06, R21, R03, and the round-trip."""

from __future__ import annotations

import pandas as pd

from provenance.io.counter_repair import cumulate, difference, repair_counter

_Q = pd.Timedelta(minutes=15)


def _series(values: list[float], *, start: str = "2026-02-01T00:00:00", freq: str = "15min"):
    idx = pd.date_range(start=start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype="float64")


def test_difference_and_cumulate_round_trip() -> None:
    cumulative = _series([100.0, 103.0, 107.0, 110.0, 118.0])
    recovered = cumulate(difference(cumulative))
    pd.testing.assert_series_equal(recovered, cumulative)


def test_clean_counter_has_no_events() -> None:
    result = repair_counter(_series([10.0, 12.0, 15.0, 20.0]), counter_id="c", column="cars")
    assert result.events.empty
    assert result.n_resets == 0 and result.n_nonmonotonic == 0
    assert result.per_interval.tolist() == [0.0, 2.0, 3.0, 5.0]


def test_reset_is_recognised_as_r05() -> None:
    # A drop to near zero is a counter reset, not a data error.
    result = repair_counter(_series([1000.0, 1005.0, 3.0, 8.0]), counter_id="c", column="cars")
    assert result.n_resets == 1
    assert set(result.events["reason_code"]) == {"R05"}
    assert result.per_interval.tolist() == [0.0, 5.0, 3.0, 5.0]


def test_small_backward_step_is_r06_nonmonotonic() -> None:
    result = repair_counter(_series([1000.0, 1005.0, 1002.0, 1010.0]))
    assert result.n_nonmonotonic == 1
    assert set(result.events["reason_code"]) == {"R06"}
    assert result.per_interval.tolist()[2] == 0.0  # clamped, not negative throughput


def test_duplicate_timestamp_is_r03() -> None:
    idx = pd.to_datetime(
        ["2026-02-01T00:00", "2026-02-01T00:15", "2026-02-01T00:15", "2026-02-01T00:30"]
    )
    series = pd.Series([10.0, 12.0, 13.0, 15.0], index=idx)
    result = repair_counter(series)
    assert result.n_duplicates == 1
    assert "R03" in set(result.events["reason_code"])


def test_dead_sensor_is_r21() -> None:
    # A counter that never advances across a week (672 quarter-hours) is dead.
    result = repair_counter(_series([500.0] * 700))
    assert result.is_dead
    assert "R21" in set(result.events["reason_code"])


def test_out_of_order_rows_flagged_r04() -> None:
    idx = pd.to_datetime(["2026-02-01T00:00", "2026-02-01T00:30", "2026-02-01T00:15"])
    series = pd.Series([10.0, 20.0, 15.0], index=idx)
    result = repair_counter(series)
    assert "R04" in set(result.events["reason_code"])
