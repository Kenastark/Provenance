"""Split conformal prediction: coverage within tolerance, and the quantile itself."""

from __future__ import annotations

import numpy as np
import pytest

from provenance.models.conformal import (
    SplitConformal,
    calibrate,
    conformal_quantile,
    empirical_coverage,
)


def test_conformal_quantile_matches_the_order_statistic() -> None:
    scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])  # n = 9
    # k = ceil((n+1)(1-alpha)) = ceil(10 * 0.9) = 9 -> the 9th smallest score.
    assert conformal_quantile(scores, alpha=0.1) == 9.0
    # ceil(10 * 0.7) = 7 -> the 7th smallest.
    assert conformal_quantile(scores, alpha=0.3) == 7.0


def test_quantile_is_infinite_when_n_too_small() -> None:
    # n = 3, 1-alpha = 0.9 -> k = ceil(4*0.9) = 4 > 3 -> cannot certify: inf.
    assert conformal_quantile([1.0, 2.0, 3.0], alpha=0.1) == float("inf")


def test_normalised_coverage_is_within_tolerance() -> None:
    # A held-out CALIBRATION block and a strictly-later TEST block (never shuffled).
    rng = np.random.default_rng(0)
    n = 4000
    sigma_true = 1.0 + 0.5 * np.arange(n) / n  # heteroscedastic
    y = rng.normal(0.0, sigma_true)
    yhat = np.zeros(n)
    cal, test = slice(0, 2000), slice(2000, n)
    cc = calibrate(y[cal], yhat[cal], sigma=sigma_true[cal], alpha=0.1)
    cov = empirical_coverage(cc, y[test], yhat[test], sigma_true[test])
    # Nominal 90% -> empirical within [85%, 95%] (the phase gate's tolerance).
    assert 0.85 <= cov <= 0.95
    assert cc.normalised is True


def test_higher_alpha_gives_a_tighter_interval() -> None:
    rng = np.random.default_rng(1)
    y = rng.normal(0.0, 1.0, size=2000)
    yhat = np.zeros(2000)
    tight = calibrate(y, yhat, alpha=0.3)
    loose = calibrate(y, yhat, alpha=0.05)
    assert tight.q < loose.q  # 70% interval is narrower than a 95% one


def test_interval_and_covers_are_consistent() -> None:
    cc = SplitConformal(alpha=0.1, q=2.0, normalised=False, n_calibration=100)
    lo, hi = cc.interval(np.array([0.0, 10.0]))
    assert np.allclose(lo, [-2.0, 8.0])
    assert np.allclose(hi, [2.0, 12.0])
    covered = cc.covers(np.array([1.5, 20.0]), np.array([0.0, 10.0]))
    assert covered.tolist() == [True, False]


def test_calibration_refuses_too_few_points() -> None:
    with pytest.raises(ValueError, match="at least"):
        calibrate([0.1, 0.2], [0.0, 0.0], alpha=0.1, min_calibration=20)


def test_normalised_interval_requires_sigma() -> None:
    cc = calibrate(
        [0.1, 0.5, 0.9, 0.3], [0.0, 0.0, 0.0, 0.0], sigma=[1.0, 1.0, 1.0, 1.0], alpha=0.5
    )
    with pytest.raises(ValueError, match="sigma"):
        cc.interval(np.array([0.0]))
