"""Split (inductive) conformal prediction for regression, with a coverage guarantee.

Given a held-out calibration set of ``n`` points, the nonconformity score is the
absolute residual ``|y - ŷ|`` — or the *normalised* residual ``|y - ŷ| / σ`` when the
model reports a predictive standard deviation, which gives adaptive, heteroscedastic
intervals (wider where the model is unsure). The conformal quantile is the exact
finite-sample order statistic

    q = the ⌈(n+1)(1-α)⌉-th smallest score              (∞ if that index exceeds n)

so that a fresh exchangeable point lands in ``ŷ ± q`` (or ``ŷ ± q·σ``) with probability
at least ``1 - α``. Nothing here is fit to the data beyond that one quantile; the
guarantee is distribution-free.

The calibration set must be a held-out **time** block (standing rule 7): passing a
random slice would silently break exchangeability for a time series and inflate the
apparent coverage. Callers draw calibration from a later block than training via
``models.cv.time_blocked_splits``; this module only computes the quantile and the
interval, and reports the *achieved* empirical coverage (never an accuracy figure).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


def conformal_quantile(scores: ArrayLike, alpha: float) -> float:
    """The finite-sample conformal quantile of ``scores`` at miscoverage ``alpha``.

    Returns ``inf`` when ``n`` is too small to certify ``1-α`` coverage (the honest
    outcome: the interval must cover everything rather than pretend to a level the data
    cannot support).
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}.")
    s = np.sort(np.asarray(scores, dtype="float64"))
    n = s.size
    if n == 0:
        raise ValueError("Cannot calibrate a conformal quantile on an empty score set.")
    k = math.ceil((n + 1) * (1.0 - alpha))
    if k > n:
        return math.inf
    return float(s[k - 1])  # k-th smallest, 1-indexed


@dataclass(frozen=True, slots=True)
class SplitConformal:
    """A calibrated interval half-width. ``normalised`` ⇒ the half-width scales with σ."""

    alpha: float
    q: float
    normalised: bool
    n_calibration: int

    def interval(
        self, mean: ArrayLike, sigma: ArrayLike | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Lower and upper bounds for predictions ``mean`` (and ``sigma`` if normalised)."""
        mean_a = np.asarray(mean, dtype="float64")
        if self.normalised:
            if sigma is None:
                raise ValueError("A normalised conformal interval needs the predictive sigma.")
            half = self.q * np.asarray(sigma, dtype="float64")
        else:
            half = np.full_like(mean_a, self.q)
        return mean_a - half, mean_a + half

    def covers(self, y: ArrayLike, mean: ArrayLike, sigma: ArrayLike | None = None) -> np.ndarray:
        """Boolean array: does the interval around ``mean`` contain ``y``?"""
        lo, hi = self.interval(mean, sigma)
        y_a = np.asarray(y, dtype="float64")
        return (y_a >= lo) & (y_a <= hi)

    def to_dict(self) -> dict[str, object]:
        return {
            "alpha": self.alpha,
            "nominal_coverage": round(1.0 - self.alpha, 4),
            "q": None if math.isinf(self.q) else round(self.q, 6),
            "normalised": self.normalised,
            "n_calibration": self.n_calibration,
        }


def calibrate(
    y: ArrayLike,
    mean: ArrayLike,
    *,
    sigma: ArrayLike | None = None,
    alpha: float = 0.1,
    min_calibration: int = 1,
) -> SplitConformal:
    """Calibrate a :class:`SplitConformal` on held-out ``(y, mean[, sigma])``.

    ``sigma`` given ⇒ a normalised (adaptive) interval; absent ⇒ a constant-width one.
    Raises if the calibration set is smaller than ``min_calibration`` — an interval
    from a handful of points would be meaningless (and would silently under-cover).
    """
    y_a = np.asarray(y, dtype="float64")
    mean_a = np.asarray(mean, dtype="float64")
    if y_a.shape != mean_a.shape:
        raise ValueError(f"y and mean shapes disagree: {y_a.shape} vs {mean_a.shape}.")
    n = y_a.size
    if n < min_calibration:
        raise ValueError(
            f"Calibration set has {n} points; need at least {min_calibration}. Refusing to "
            "produce an interval that cannot be trusted (draw a larger held-out time block)."
        )
    residual = np.abs(y_a - mean_a)
    normalised = sigma is not None
    if normalised:
        sig = np.asarray(sigma, dtype="float64")
        sig = np.where(sig <= 1e-12, 1e-12, sig)
        scores = residual / sig
    else:
        scores = residual
    q = conformal_quantile(scores, alpha)
    return SplitConformal(alpha=alpha, q=q, normalised=normalised, n_calibration=n)


def empirical_coverage(
    conformal: SplitConformal,
    y: ArrayLike,
    mean: ArrayLike,
    sigma: ArrayLike | None = None,
) -> float:
    """The fraction of held-out ``y`` the calibrated interval actually covers."""
    covered = conformal.covers(y, mean, sigma)
    return float(np.mean(covered)) if covered.size else float("nan")
