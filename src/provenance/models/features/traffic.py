"""Traffic covariate: the repaired Enclod counters, when they are available.

Roadside vehicle throughput is a genuine driver of a station's pollutant levels, so
it belongs in the feature set. But the Enclod counter schema is unconfirmed (ADR
0003) and its adapter fails loudly rather than guess column names, so in this phase
the traffic feature is almost always a flagged placeholder.

This module makes that honest: given per-interval counts recovered by
``io.counter_repair`` it produces an hourly traffic-flow feature; given nothing it
produces a constant, imputed column marked ``available=False``. A zero here is never
mistaken for "no traffic" — it is "we could not read the traffic feed", and the
model card says so.
"""

from __future__ import annotations

import pandas as pd

TRAFFIC_FLOW = "traffic_flow"

# The imputation constant for the unavailable case. A single constant column carries
# no information, so the tree models cannot lean on it; it is present only so the
# feature name and provenance stay stable whether or not the feed is confirmed.
_IMPUTED_FLOW = 0.0


def traffic_feature(
    timestamps: pd.DatetimeIndex,
    per_interval: pd.Series | None = None,
) -> tuple[pd.Series, bool]:
    """Return the hourly ``traffic_flow`` column and whether it is real.

    ``per_interval`` is the reset-aware per-interval count series from
    ``io.counter_repair`` (15-minute cadence). It is summed to the hourly grid and
    aligned to ``timestamps``. When ``None`` (the confirmed-feed-not-yet case) a
    constant imputed column is returned with ``available=False``.
    """
    ts = pd.DatetimeIndex(timestamps)
    if per_interval is None or per_interval.empty:
        return pd.Series(_IMPUTED_FLOW, index=ts, name=TRAFFIC_FLOW), False
    hourly = per_interval.copy()
    hourly.index = pd.to_datetime(hourly.index)
    hourly = hourly.resample("h").sum()
    aligned = hourly.reindex(ts).astype("float64")
    # A genuinely absent hour is imputed to the series median so a single gap does not
    # read as zero traffic; the provenance stays TRAFFIC (real feed, one gap filled).
    aligned = aligned.fillna(float(hourly.median()) if not hourly.empty else _IMPUTED_FLOW)
    aligned.name = TRAFFIC_FLOW
    return aligned, True
