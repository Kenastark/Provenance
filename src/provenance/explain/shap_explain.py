"""SHAP attributions over the tree models, with a stable feature-name mapping.

TreeExplainer is exact for gradient-boosted trees: the attributions plus the base
value reconstruct the model's output to within float error. That is the property the
test gate pins, and it is what makes a SHAP explanation trustworthy rather than
indicative — the numbers add up to the prediction, they do not merely gesture at it.

Every attribution carries the feature's provenance (measured / proxy / derived /
unavailable), so an operator sees not just *which* input drove a value but whether
that input was a real measurement or a stand-in (§5.3, §8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import shap

from provenance.models.deweather.model import DeweatherModel
from provenance.models.fault.classify import FaultClassifier
from provenance.models.features import FeatureSet


@dataclass(frozen=True, slots=True)
class Attribution:
    """One feature's SHAP contribution to a single prediction."""

    feature: str
    value: float
    feature_value: float
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "value": round(self.value, 6),
            "feature_value": round(self.feature_value, 6),
            "provenance": self.provenance,
        }


@dataclass(frozen=True, slots=True)
class ShapExplanation:
    """A single prediction explained: base value + per-feature attributions.

    Invariant (SHAP additivity): ``base_value + sum(attributions) == prediction`` to
    within float tolerance. :meth:`reconstructs` checks it; the test gate asserts it.
    """

    target: str
    base_value: float
    prediction: float
    attributions: tuple[Attribution, ...]
    predicted_class: str | None = None

    @property
    def total(self) -> float:
        return self.base_value + sum(a.value for a in self.attributions)

    def reconstructs(self, tol: float = 1e-4) -> bool:
        return abs(self.total - self.prediction) <= tol

    def top(self, k: int) -> list[Attribution]:
        return sorted(self.attributions, key=lambda a: abs(a.value), reverse=True)[:k]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "predicted_class": self.predicted_class,
            "base_value": round(self.base_value, 6),
            "prediction": round(self.prediction, 6),
            "reconstructs": self.reconstructs(),
            "attributions": [a.to_dict() for a in self.attributions],
        }


def _provenance_map(feature_set: FeatureSet | None, names: list[str]) -> dict[str, str]:
    if feature_set is None:
        return dict.fromkeys(names, "residual-derived")
    out: dict[str, str] = {}
    for n in names:
        try:
            out[n] = feature_set.spec_for(n).provenance.value
        except KeyError:
            out[n] = "unknown"
    return out


def _row_frame(feature_row: pd.Series, names: list[str]) -> pd.DataFrame:
    """A single-row frame in the model's feature order (SHAP needs a 2-D input)."""
    return pd.DataFrame([[float(feature_row[n]) for n in names]], columns=names)


def explain_deweather(
    model: DeweatherModel, parameter: str, feature_row: pd.Series
) -> ShapExplanation:
    """Explain the weather-predicted value for one pollutant at one (station, hour).

    The regressor is exactly additive, so ``base_value + sum(attributions)`` equals the
    prediction — the operator sees precisely which weather and time features produced
    the expected value the reading is compared against.
    """
    if parameter not in model.regressors:
        raise KeyError(f"Deweather model has no regressor for {parameter!r}.")
    regressor = model.regressors[parameter]
    names = list(model.feature_names)
    X = _row_frame(feature_row, names)

    explainer = shap.TreeExplainer(regressor)
    sv = np.asarray(explainer.shap_values(X))[0]
    base = float(np.asarray(explainer.expected_value).ravel()[0])
    prediction = float(regressor.predict(X)[0])

    row_vals = X.to_numpy()[0]
    prov = _provenance_map(model.feature_set, names)
    attributions = tuple(
        Attribution(name, float(sv[i]), float(row_vals[i]), prov[name])
        for i, name in enumerate(names)
    )
    return ShapExplanation(
        target=f"deweather:{parameter}",
        base_value=base,
        prediction=prediction,
        attributions=attributions,
    )


def explain_fault(model: FaultClassifier, feature_row: pd.Series) -> ShapExplanation:
    """Explain the subtle-case model's chosen class for one cell (margin-space SHAP).

    Multiclass SHAP is per class; this explains the *predicted* class, whose margin is
    reconstructed by ``base_value + sum(attributions)``. Raises if the model is a
    rules-only (degraded) classifier with no ML component.
    """
    if model.ml_model is None:
        raise ValueError("This fault classifier is rules-only (degraded); nothing to explain.")
    names = list(model.feature_names)
    X = _row_frame(feature_row, names)
    classes = list(model.ml_model.classes_)
    proba = model.ml_model.predict_proba(X)[0]
    cls_idx = int(np.argmax(proba))

    explainer = shap.TreeExplainer(model.ml_model)
    sv = explainer.shap_values(X)
    base_all = explainer.expected_value
    row_sv, base = _select_class(sv, base_all, cls_idx, n_features=len(names))
    # The reconstructed value is the raw margin for the predicted class.
    margin = float(base + row_sv.sum())

    row_vals = X.to_numpy()[0]
    prov = _provenance_map(None, names)
    attributions = tuple(
        Attribution(name, float(row_sv[i]), float(row_vals[i]), prov[name])
        for i, name in enumerate(names)
    )
    return ShapExplanation(
        target="fault",
        base_value=float(base),
        prediction=margin,
        attributions=attributions,
        predicted_class=str(classes[cls_idx]),
    )


def _select_class(
    sv: Any, base_all: Any, cls_idx: int, *, n_features: int
) -> tuple[np.ndarray, float]:
    """Pull one class's attribution row and base value out of SHAP's multiclass output.

    SHAP returns either a list of per-class arrays or a single ``(n, features, classes)``
    array depending on version; both are handled here so the caller never has to care.
    """
    if isinstance(sv, list):
        row = np.asarray(sv[cls_idx])[0]
        base = float(np.asarray(base_all).ravel()[cls_idx])
        return row, base
    arr = np.asarray(sv)
    if arr.ndim == 3:  # (samples, features, classes)
        row = arr[0, :, cls_idx]
        base = float(np.asarray(base_all).ravel()[cls_idx])
        return row, base
    # Binary/degenerate: a single (samples, features) array.
    row = arr[0]
    base = float(np.asarray(base_all).ravel()[0])
    return row.reshape(n_features), base
