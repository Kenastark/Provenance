"""Time-blocked CV and the leakage guard — including testing the test.

The guard is only worth anything if it actually rejects a bad split, so this asserts
both directions: the honest forward-chaining split passes, and a deliberately shuffled
(random-K-fold-style) split raises.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from provenance.models.cv import LeakageError, assert_no_leakage, time_blocked_splits

pytestmark = pytest.mark.unit


def _hourly(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-05-01", periods=n, freq="h")


def test_time_blocked_splits_are_forward_chaining() -> None:
    ts = _hourly(100)
    splits = time_blocked_splits(ts, n_splits=4)
    assert len(splits) == 4
    for train_idx, test_idx in splits:
        assert ts[train_idx].max() < ts[test_idx].min()  # strictly before, every fold


def test_honest_split_passes_the_guard() -> None:
    ts = _hourly(100)
    assert_no_leakage(ts, time_blocked_splits(ts, n_splits=4))  # must not raise


def test_shuffled_split_is_rejected() -> None:
    """Testing the test: a random-K-fold-style shuffled split must fail the guard."""
    ts = _hourly(100)
    rng = np.random.RandomState(0)
    perm = rng.permutation(100)
    leaky = [(perm[:50], perm[50:])]
    with pytest.raises(LeakageError, match="forward-chaining"):
        assert_no_leakage(ts, leaky)


def test_ties_do_not_straddle_a_boundary() -> None:
    """Many rows sharing a timestamp (the multi-station grid) never split across a fold."""
    times = np.repeat(_hourly(20).values, 6)  # 6 stations per hour
    splits = time_blocked_splits(times, n_splits=3)
    assert_no_leakage(times, splits)
    for train_idx, test_idx in splits:
        assert set(pd.DatetimeIndex(times[train_idx])).isdisjoint(
            set(pd.DatetimeIndex(times[test_idx]))
        )


def test_too_few_timestamps_raises() -> None:
    with pytest.raises(ValueError, match="distinct timestamps"):
        time_blocked_splits(_hourly(3), n_splits=4)
