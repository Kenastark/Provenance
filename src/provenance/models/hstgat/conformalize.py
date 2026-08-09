"""Wrap the HST-GAT's outputs with a calibrated interval (§7.7).

This is where the model and split conformal meet: the HST-GAT predicts a mean and a σ
for each station-hour, and conformal turns that σ into an interval with a real coverage
guarantee. The calibration and test sets are **held-out time blocks** (standing rule 7),
forward-chained — never a random slice — so the achieved coverage the model card reports
is honest for a time series.

The normalised score ``|y - ŷ| / σ`` gives adaptive intervals: wider where the model is
unsure, narrower where it is confident, which is exactly what a trust score wants when it
carries the interval to an operator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from provenance.models.conformal import SplitConformal, calibrate, empirical_coverage
from provenance.models.cv import time_blocked_splits
from provenance.models.hstgat.data import TemporalGraphBatch

if TYPE_CHECKING:  # pragma: no cover
    from torch import nn


def _predict_block(
    model: nn.Module, mean: float, std: float, batch: TemporalGraphBatch, rows: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reconstruct the (standardised) target on ``rows`` (a set of hour indices).

    Returns ``(y, yhat, sigma)`` in the physical unit over the observed cells of those
    hours — the graph-conditioned expectation with every cell in the block hidden.
    """
    import torch

    row_mask = torch.zeros(batch.n_times, dtype=torch.bool)
    row_mask[torch.tensor(rows, dtype=torch.long)] = True
    hidden = batch.observed & row_mask.unsqueeze(-1)
    value_input = torch.where(hidden, torch.zeros_like(batch.target), batch.target)
    mask_flag = hidden.to(batch.target.dtype)
    with torch.no_grad():
        fc = model(value_input, mask_flag, batch)
    sel = hidden
    y = (batch.target[sel].numpy() * std) + mean
    yhat = (fc.mean[sel].numpy() * std) + mean
    sigma = np.sqrt(fc.variance[sel].numpy()) * std
    return y, yhat, sigma


def calibrate_and_coverage(
    model: nn.Module,
    mean: float,
    std: float,
    batch: TemporalGraphBatch,
    *,
    alpha: float = 0.1,
    n_splits: int = 3,
    min_calibration: int = 20,
) -> tuple[SplitConformal | None, dict[str, Any]]:
    """Calibrate a normalised conformal interval on one held-out block, score on the next.

    Returns ``(conformal, report)``. ``conformal`` is ``None`` (and the report says why)
    when there are too few hours to form two forward-chained blocks or too few
    calibration points to trust — the honest refusal, not a fabricated interval.
    """
    times = pd.DatetimeIndex(batch.times)
    try:
        splits = time_blocked_splits(times, n_splits=max(2, n_splits))
    except ValueError as exc:
        return None, {"calibrated": False, "reason": str(exc)}
    if len(splits) < 2:
        return None, {"calibrated": False, "reason": "need at least two forward-chained blocks"}

    _, calib_rows = splits[-2]
    _, test_rows = splits[-1]
    y_cal, yhat_cal, sig_cal = _predict_block(model, mean, std, batch, calib_rows)
    if y_cal.size < min_calibration:
        return None, {
            "calibrated": False,
            "reason": f"only {int(y_cal.size)} calibration points (need {min_calibration})",
        }
    conformal = calibrate(
        y_cal, yhat_cal, sigma=sig_cal, alpha=alpha, min_calibration=min_calibration
    )
    y_test, yhat_test, sig_test = _predict_block(model, mean, std, batch, test_rows)
    coverage = empirical_coverage(conformal, y_test, yhat_test, sig_test)
    report = {
        "calibrated": True,
        "alpha": alpha,
        "nominal_coverage": round(1.0 - alpha, 4),
        "empirical_coverage": None if np.isnan(coverage) else round(float(coverage), 4),
        "n_calibration": int(y_cal.size),
        "n_test": int(y_test.size),
        **conformal.to_dict(),
    }
    return conformal, report
