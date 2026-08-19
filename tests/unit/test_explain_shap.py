"""SHAP explainability tests: shape, stability, and exact reconstruction.

TreeExplainer is additive by construction, so the strongest assertion is the simplest:
base value plus the attributions reconstruct the model's own prediction. Shape matches
the feature count, and two seeded runs are byte-identical.
"""

from __future__ import annotations

import pytest

from provenance.explain import explain_deweather, explain_fault, operator_sentence
from provenance.models.features import build_features

pytestmark = pytest.mark.unit


def _feature_row(trained_models: dict[str, object], pos: int = 500):
    frame = trained_models["frame"]
    weather = trained_models["weather"]
    matrix, _ = build_features(frame, weather=weather)  # type: ignore[arg-type]
    return matrix.iloc[pos]


def test_shap_shape_matches_feature_count(trained_models: dict[str, object]) -> None:
    model = trained_models["deweather"]
    ex = explain_deweather(model, "PM10", _feature_row(trained_models))  # type: ignore[arg-type]
    assert len(ex.attributions) == len(model.feature_names)  # type: ignore[attr-defined]


def test_shap_reconstructs_prediction(trained_models: dict[str, object]) -> None:
    model = trained_models["deweather"]
    for pos in (10, 500, 2000):
        ex = explain_deweather(model, "PM10", _feature_row(trained_models, pos))  # type: ignore[arg-type]
        assert ex.reconstructs(tol=1e-4), (ex.total, ex.prediction)


def test_shap_is_stable_across_seeded_runs(trained_models: dict[str, object]) -> None:
    model = trained_models["deweather"]
    row = _feature_row(trained_models)
    a = explain_deweather(model, "PM10", row)  # type: ignore[arg-type]
    b = explain_deweather(model, "PM10", row)  # type: ignore[arg-type]
    for x, y in zip(a.attributions, b.attributions, strict=True):
        assert x.feature == y.feature
        assert abs(x.value - y.value) < 1e-12


def test_operator_sentence_names_top_features(trained_models: dict[str, object]) -> None:
    model = trained_models["deweather"]
    ex = explain_deweather(model, "PM10", _feature_row(trained_models))  # type: ignore[arg-type]
    sentence = operator_sentence(ex, top_k=3)
    assert sentence.startswith("Driven primarily by")
    assert sentence.endswith(".")
    assert "{" not in sentence  # no unfilled placeholders
    assert " by by " not in sentence  # the double-"by" regression must not return


def test_fault_shap_reconstructs_margin(trained_models: dict[str, object]) -> None:
    from provenance.models.fault.classify import fault_features

    deweather = trained_models["deweather"]
    fault = trained_models["fault"]
    frame = trained_models["frame"]
    weather = trained_models["weather"]
    resid = deweather.predict_series(frame, weather=weather)  # type: ignore[attr-defined]
    ff = fault_features(resid)
    ex = explain_fault(fault, ff.iloc[1000])  # type: ignore[arg-type]
    assert len(ex.attributions) == len(fault.feature_names)  # type: ignore[attr-defined]
    assert ex.predicted_class is not None
    assert ex.reconstructs(tol=1e-3)  # additive in margin space
