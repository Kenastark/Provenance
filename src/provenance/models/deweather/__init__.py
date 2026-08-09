"""Deweathering (B2): separate the weather from the pollution.

A raw pollutant reading conflates two things — what the source emitted and what the
weather did to it. A calm, low-mixing-layer night concentrates whatever is there; a
windy afternoon dilutes it. Comparing raw values across such hours flags the weather,
not the sensor.

The deweather model predicts each pollutant from meteorology and time alone. The
**residual** it leaves behind — actual minus weather-predicted — is what anomaly
detection should see (§7.6): the part of the reading the weather does *not* explain.

Trained forward-chaining only (:mod:`provenance.models.cv`), never random K-fold, and
held to an R² sanity band: too low means weather isn't being captured, too high means
no genuine signal is left to find. Both are failures, and the test gate names which.
"""

from __future__ import annotations

from provenance.models.deweather.model import (
    DeweatherModel,
    PollutantMetrics,
    train_deweather,
)
from provenance.models.deweather.residuals import (
    residual_frame,
    store_residuals,
)

__all__ = [
    "DeweatherModel",
    "PollutantMetrics",
    "residual_frame",
    "store_residuals",
    "train_deweather",
]
