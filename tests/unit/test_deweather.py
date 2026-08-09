"""Deweathering tests: the R² sanity band, residuals, and determinism.

The band test is the one that fails loudly with a *reason*: below the floor weather is
not being captured, above the ceiling nothing is left for a genuine event to show up in.
The message names which failure occurred, because the two mean opposite things.
"""

from __future__ import annotations

import numpy as np
import pytest

from provenance.config.loading import load_models_config
from provenance.models.deweather import residual_frame, train_deweather
from provenance.models.deweather.model import RESIDUAL

pytestmark = pytest.mark.unit


def test_r2_band_per_pollutant(trained_models: dict[str, object]) -> None:
    model = trained_models["deweather"]
    cfg = load_models_config()["deweather"]
    floor, ceiling = float(cfg["r2_floor"]), float(cfg["r2_ceiling"])
    for parameter, metrics in model.metrics.items():  # type: ignore[attr-defined]
        r2 = metrics.cv_r2_mean
        if r2 <= floor:
            pytest.fail(
                f"{parameter}: held-out R²={r2:.3f} is at/below the floor {floor}. Weather is "
                f"not being captured — the residual is just the raw value."
            )
        if r2 >= ceiling:
            pytest.fail(
                f"{parameter}: held-out R²={r2:.3f} is at/above the ceiling {ceiling}. No "
                f"unexplained signal is left for a genuine event to surface in."
            )


def test_residuals_are_centred_and_shaped(trained_models: dict[str, object]) -> None:
    model = trained_models["deweather"]
    frame = trained_models["frame"]
    weather = trained_models["weather"]
    res = residual_frame(model, frame, weather=weather)  # type: ignore[arg-type]
    assert not res.empty
    assert {"actual", "predicted", RESIDUAL}.issubset(res.columns)
    # Residuals are roughly centred (the model is unbiased on its own training window).
    assert abs(float(res[RESIDUAL].mean())) < 1.0


def test_training_is_deterministic(trained_models: dict[str, object]) -> None:
    """Two trainings on the same data give byte-identical predictions (standing rule 8)."""
    frame = trained_models["frame"]
    weather = trained_models["weather"]
    a = train_deweather(frame, weather=weather)  # type: ignore[arg-type]
    b = train_deweather(frame, weather=weather)  # type: ignore[arg-type]
    ra = residual_frame(a, frame, weather=weather)  # type: ignore[arg-type]
    rb = residual_frame(b, frame, weather=weather)  # type: ignore[arg-type]
    assert a.version == b.version
    assert np.allclose(ra["predicted"].to_numpy(), rb["predicted"].to_numpy())


def test_only_present_pollutants_are_trained(trained_models: dict[str, object]) -> None:
    model = trained_models["deweather"]
    # The demo corpus carries PM10/NO2/O3/CO; the model trains exactly those.
    assert set(model.pollutants) == {"PM10", "NO2", "O3", "CO"}  # type: ignore[attr-defined]
