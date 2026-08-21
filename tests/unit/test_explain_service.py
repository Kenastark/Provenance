"""explain_defect's method routing: model, rule, and the metadata-only carve-out.

R07-R09 keep the weather-SHAP explanation even though the flag itself is a
deterministic rule (§8's "impossible reading, ML precedence" design): "how far is
this from what weather predicts" is informative context for a magnitude anomaly.
R10/R11 are different - they flag the reading's declared unit or detection limit,
not its magnitude - so they must never reach the model path even when their
pollutant is otherwise covered, or the SHAP sentence would explain a completely
unrelated, well-predicted number.
"""

from __future__ import annotations

import pandas as pd
import pytest

from provenance.explain.service import DefectRef, explain_defect
from provenance.models.registry import ModelBundle
from provenance.schema import canonical as C

pytestmark = pytest.mark.unit


def _pm10_ref(trained_models: dict[str, object], reason_code: str) -> DefectRef:
    frame = trained_models["frame"]
    row = frame[frame[C.PARAMETER] == "PM10"].iloc[500]  # type: ignore[index]
    return DefectRef(
        defect_id=1,
        station_id=str(row[C.STATION_ID]),
        parameter="PM10",
        timestamp_utc=pd.Timestamp(row[C.TIMESTAMP]),
        reason_code=reason_code,
        evidence={},
    )


def _bundle(trained_models: dict[str, object]) -> ModelBundle:
    return ModelBundle(
        deweather=trained_models["deweather"],  # type: ignore[arg-type]
        fault=trained_models["fault"],  # type: ignore[arg-type]
    )


def test_metadata_only_code_skips_the_model_path(trained_models: dict[str, object]) -> None:
    """R10 on a covered pollutant still gets the deterministic reason, not SHAP."""
    frame = trained_models["frame"]
    ref = _pm10_ref(trained_models, "R10")
    result = explain_defect(frame, ref, _bundle(trained_models))  # type: ignore[arg-type]
    assert result.method == "rule"
    assert result.shap is None
    assert not result.degraded
    assert any("declared unit or detection limit" in n for n in result.notes)


def test_metadata_only_code_r11_also_skips_the_model_path(
    trained_models: dict[str, object],
) -> None:
    frame = trained_models["frame"]
    ref = _pm10_ref(trained_models, "R11")
    result = explain_defect(frame, ref, _bundle(trained_models))  # type: ignore[arg-type]
    assert result.method == "rule"
    assert result.shap is None


def test_magnitude_codes_still_use_the_model_path(trained_models: dict[str, object]) -> None:
    """R07 (physical maximum) is unaffected: it keeps the weather-SHAP context that
    motivated the original design (see test_explain_api.py's API-level equivalent)."""
    frame = trained_models["frame"]
    ref = _pm10_ref(trained_models, "R07")
    result = explain_defect(frame, ref, _bundle(trained_models))  # type: ignore[arg-type]
    assert result.method == "model"
    assert result.shap is not None
