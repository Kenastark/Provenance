"""Cumulative traffic-counter repair.

The Enclod roadside counters report a *running total* per vehicle class, sampled
every 15 minutes. A running total is not a measurement you can audit directly:
you have to difference it to recover per-interval counts, and differencing a
counter that resets (~80-96 times per column) or occasionally ticks backwards
produces garbage unless it is reset-aware. This module is that step.

It is deliberately a small, pure unit over a single cumulative series so it can
be tested exhaustively:

* ``difference`` / ``cumulate`` are exact inverses on a clean monotonic series
  (the round-trip property the test gate requires).
* ``repair_counter`` handles duplicate timestamps (R03), out-of-order rows (R04),
  resets (R05), non-monotonic backward steps (R06), and dead sensors (R21).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from provenance.config.loading import load_thresholds

# A decrease is a reset (not a data error) when the new value falls to at most
# this fraction of the previous total - i.e. the counter restarted near zero
# rather than ticking backward by a few counts.
_RESET_RATIO = 0.5
_QUARTER_HOUR = pd.Timedelta(minutes=15)


def difference(cumulative: pd.Series) -> pd.Series:
    """Per-interval counts from a cumulative series, exactly invertible.

    The first element is kept as-is so that ``cumulate(difference(x)) == x`` for
    any clean (sorted, monotonic, gap-free) input - the round-trip guarantee.
    """
    diffs = cumulative.diff()
    diffs.iloc[0] = cumulative.iloc[0]
    return diffs


def cumulate(per_interval: pd.Series) -> pd.Series:
    """Inverse of :func:`difference`: rebuild the running total."""
    return per_interval.cumsum()


@dataclass(frozen=True, slots=True)
class CounterRepairResult:
    counter_id: str
    column: str
    per_interval: pd.Series
    """Reconstructed non-negative per-interval counts, indexed by timestamp."""
    events: pd.DataFrame
    """Columns: reason_code, timestamp_utc, evidence (dict)."""
    n_observed: int
    n_resets: int
    n_nonmonotonic: int
    n_duplicates: int
    is_dead: bool
    completeness: float
    meta: dict[str, object] = field(default_factory=dict)


def _event(code: str, ts: pd.Timestamp, **evidence: object) -> dict[str, object]:
    return {"reason_code": code, "timestamp_utc": ts, "evidence": evidence}


def repair_counter(
    cumulative: pd.Series,
    *,
    counter_id: str = "",
    column: str = "",
    interval: pd.Timedelta | None = None,
) -> CounterRepairResult:
    """Repair one cumulative counter series into per-interval counts.

    ``cumulative`` is indexed by timestamp. The index need not be sorted, unique,
    or gap-free; this function makes it so and records what it had to fix.
    ``interval`` defaults to the 15-minute Enclod sampling cadence.
    """
    interval = interval if interval is not None else _QUARTER_HOUR
    thresholds = load_thresholds()
    dead_min = int(thresholds["sensor_dead"]["dead_min_consecutive_intervals"])
    events: list[dict[str, object]] = []

    series = cumulative.copy()
    series.index = pd.to_datetime(series.index)

    # R04: out-of-order rows. Detect before sorting so we can report it.
    if not series.index.is_monotonic_increasing:
        # Any row timestamped earlier than the running maximum is out of order.
        running_max = series.index.to_series().cummax()
        for ts in series.index[
            series.index.to_series() < running_max.shift(fill_value=series.index[0])
        ]:
            events.append(_event("R04", ts, note="timestamp precedes an earlier row"))

    # R03: duplicate timestamps. Keep the last (highest cumulative) reading.
    dup_mask = series.index.duplicated(keep="last")
    n_duplicates = int(dup_mask.sum())
    for ts in pd.Index(series.index[series.index.duplicated(keep=False)]).unique():
        vals = series[series.index == ts].tolist()
        if len(vals) > 1:
            events.append(_event("R03", ts, values=vals))
    series = series[~dup_mask]
    series = series.sort_index()

    values = series.to_numpy(dtype="float64")
    idx = pd.DatetimeIndex(series.index)

    # Dead sensor: the running total never advances across the whole window.
    is_dead = len(values) >= dead_min and float(values.max() - values.min()) == 0.0
    if is_dead:
        events.append(
            _event("R21", idx[-1], since=idx[0].isoformat(), constant_value=float(values[0]))
        )

    per = pd.Series(0.0, index=idx, dtype="float64")
    n_resets = 0
    n_nonmonotonic = 0
    if len(values):
        per.iloc[0] = 0.0  # first sample: increment since previous epoch is unknown
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            per.iloc[i] = delta
            continue
        # delta < 0: reset or backward tick?
        if values[i] <= _RESET_RATIO * values[i - 1]:
            n_resets += 1
            events.append(
                _event("R05", idx[i], previous=float(values[i - 1]), current=float(values[i]))
            )
            per.iloc[i] = float(values[i])  # counter restarted; increment is the new value
        else:
            n_nonmonotonic += 1
            events.append(
                _event("R06", idx[i], previous=float(values[i - 1]), current=float(values[i]))
            )
            per.iloc[i] = 0.0  # clamp: a small backward step is not real throughput

    completeness = _completeness(idx, interval)
    events_df = pd.DataFrame(events, columns=["reason_code", "timestamp_utc", "evidence"])
    return CounterRepairResult(
        counter_id=counter_id,
        column=column,
        per_interval=per,
        events=events_df,
        n_observed=len(series),
        n_resets=n_resets,
        n_nonmonotonic=n_nonmonotonic,
        n_duplicates=n_duplicates,
        is_dead=is_dead,
        completeness=completeness,
    )


def _completeness(idx: pd.DatetimeIndex, interval: pd.Timedelta) -> float:
    """Observed intervals over the intervals expected across the covered span."""
    if len(idx) < 2:
        return 1.0
    span = idx[-1] - idx[0]
    expected = int(span / interval) + 1
    return round(len(idx) / expected, 6) if expected else 1.0
