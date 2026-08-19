"""Time-blocked cross-validation, and the guard that forbids leakage.

A time series must never be split with random K-fold (standing rule 7, "Never do
this" #7): shuffling rows lets a fold train on Tuesday to predict Monday, which
inflates every metric and would never survive contact with live data. The only
honest split is forward-chaining — each fold trains on the past and tests on a
strictly later block.

:func:`assert_no_leakage` is the enforcement, and it is deliberately usable as a
standalone check: the test gate feeds it both an honest split (passes) and a
deliberately shuffled one (must raise), so the guard itself is tested, not just
trusted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class LeakageError(AssertionError):
    """A CV fold trains on data at or after its own test block. Never allowed."""


def time_blocked_splits(
    timestamps: pd.Series | pd.DatetimeIndex | pd.Index | np.ndarray,
    n_splits: int = 4,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Forward-chaining splits over ``n_splits`` contiguous time blocks.

    Returns positional integer indices into ``timestamps``. Fold *k* trains on every
    row whose timestamp falls in blocks 0..k-1 and tests on block k, so by
    construction ``max(train timestamps) < min(test timestamps)`` for every fold.
    Ties (many rows sharing a timestamp — the multi-station grid) never straddle a
    boundary: blocks are cut on the sorted *unique* timestamps.
    """
    if n_splits < 1:
        raise ValueError(f"n_splits must be >= 1, got {n_splits}")
    ts = pd.DatetimeIndex(pd.to_datetime(pd.Series(np.asarray(timestamps)).reset_index(drop=True)))
    unique = np.array(sorted(ts.unique()))
    if len(unique) < n_splits + 1:
        raise ValueError(
            f"Need at least {n_splits + 1} distinct timestamps for {n_splits} time-blocked "
            f"folds; got {len(unique)}. Use fewer folds or more data."
        )
    # Cut the unique timestamps into n_splits+1 near-equal contiguous blocks.
    boundaries = np.array_split(unique, n_splits + 1)
    ts_values = ts.values
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for k in range(1, n_splits + 1):
        train_cut = boundaries[k - 1][-1]  # last timestamp of the immediately-prior block
        test_block = boundaries[k]
        test_lo, test_hi = test_block[0], test_block[-1]
        train_idx = np.nonzero(ts_values <= train_cut)[0]
        test_idx = np.nonzero((ts_values >= test_lo) & (ts_values <= test_hi))[0]
        if len(train_idx) and len(test_idx):
            splits.append((train_idx, test_idx))
    return splits


def assert_no_leakage(
    timestamps: pd.Series | pd.DatetimeIndex | pd.Index | np.ndarray,
    splits: list[tuple[np.ndarray, np.ndarray]],
) -> None:
    """Raise :class:`LeakageError` if any fold trains on data not strictly before its test.

    The honest invariant: for every fold, the latest training timestamp is earlier
    than the earliest test timestamp. A shuffled/random-K-fold split violates it and
    is rejected here rather than silently producing an optimistic score.
    """
    ts = pd.DatetimeIndex(pd.to_datetime(pd.Series(np.asarray(timestamps)).reset_index(drop=True)))
    values = ts.values
    for fold, (train_idx, test_idx) in enumerate(splits):
        if len(train_idx) == 0 or len(test_idx) == 0:
            continue
        train_max = values[train_idx].max()
        test_min = values[test_idx].min()
        if train_max >= test_min:
            raise LeakageError(
                f"Fold {fold} leaks: latest training timestamp {pd.Timestamp(train_max)} is not "
                f"strictly before the earliest test timestamp {pd.Timestamp(test_min)}. A time "
                f"series must be split forward-chaining, never with random K-fold."
            )
