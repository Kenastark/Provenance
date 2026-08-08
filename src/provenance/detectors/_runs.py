"""Shared helper: maximal runs of consecutive equal / consecutive-timestamp items.

Several detectors reduce to "find the stretches where something held" - a value
stayed frozen, an hour stayed absent. Keeping that logic in one tested place stops
each detector re-implementing an off-by-one at the run boundary.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd


def equal_value_runs(values: np.ndarray) -> Iterator[tuple[int, int]]:
    """Yield (start_index, length) for each maximal run of identical values.

    NaNs never join a run: a gap breaks the sequence.
    """
    n = len(values)
    i = 0
    while i < n:
        j = i + 1
        while j < n and values[j] == values[i] and not _isnan(values[j]) and not _isnan(values[i]):
            j += 1
        yield i, j - i
        i = j


def _isnan(x: object) -> bool:
    try:
        return bool(pd.isna(x))  # type: ignore[call-overload]
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return False


def consecutive_runs(
    timestamps: pd.DatetimeIndex, cadence: pd.Timedelta
) -> Iterator[pd.DatetimeIndex]:
    """Yield each maximal run of timestamps spaced exactly one cadence apart."""
    if len(timestamps) == 0:
        return
    ordered = pd.DatetimeIndex(sorted(timestamps))
    start = 0
    for i in range(1, len(ordered)):
        if ordered[i] - ordered[i - 1] != cadence:
            yield ordered[start:i]
            start = i
    yield ordered[start:]
