"""Fault-classifier tests: recall floors, the confusion matrix, and rule precedence.

The precedence test is the one the standing rules single out: the ML must never
override a deterministic physical-impossibility flag. It is proved with an *adversarial*
model that always votes "calibration_drift" — the impossible reading still resolves to
physically_impossible by rule, while an ordinary reading takes the model's vote, which
shows the model is genuinely consulted and genuinely overridden.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from provenance.models.fault import FaultClass, classify_faults
from provenance.models.fault.classify import FAULT_CLASS, SOURCE
from provenance.models.fault.labels import rule_class_for
from provenance.schema import canonical as C

pytestmark = pytest.mark.unit


def test_signature_recall_floors_met(trained_models: dict[str, object]) -> None:
    fault = trained_models["fault"]
    floors = fault.recall_floors  # type: ignore[attr-defined]
    recall = fault.signature_recall  # type: ignore[attr-defined]
    # Every signature the config floors must have been scored on the held-out block.
    assert set(floors) == set(recall), f"missing signatures: {set(floors) - set(recall)}"
    for kind, floor in floors.items():
        assert recall[kind] >= floor, f"{kind} recall {recall[kind]} below floor {floor}"


def test_meteo_precision_floor_met(trained_models: dict[str, object]) -> None:
    fault = trained_models["fault"]
    assert fault.meteo_precision >= fault.meteo_precision_floor  # type: ignore[attr-defined]


def test_confusion_matrix_covers_all_classes(trained_models: dict[str, object]) -> None:
    fault = trained_models["fault"]
    card = fault.to_card_dict()  # type: ignore[attr-defined]
    classes = set(FaultClass)
    cm = card["confusion_matrix"]
    assert {FaultClass(k) for k in cm} == classes  # a row per class, none dropped


def test_no_headline_accuracy_is_reported(trained_models: dict[str, object]) -> None:
    fault = trained_models["fault"]
    card = fault.to_card_dict()  # type: ignore[attr-defined]
    # Per-class metrics only; no single accuracy/f1 headline (standing rule 4).
    assert "accuracy" not in card
    assert any("headline accuracy" in n for n in card["notes"])


def test_rule_class_precedence_prefers_physical_impossibility() -> None:
    # A cell flagged both frozen (R12) and physically impossible (R07) is physical.
    assert rule_class_for({"R12", "R07"}) is FaultClass.PHYSICALLY_IMPOSSIBLE
    assert rule_class_for({"R02"}) is FaultClass.COMMUNICATION_FAILURE
    assert rule_class_for({"R14"}) is None  # a soft statistical flag decides nothing


class _AdversarialModel:
    """A stand-in ML model that always insists on calibration_drift."""

    classes_ = np.array(["calibration_drift", "meteorological_artefact", "none"])

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        out = np.zeros((len(X), 3))
        out[:, 0] = 1.0  # calibration_drift, always
        return out


def _pm10_frame() -> tuple[pd.DataFrame, pd.Timestamp]:
    """A small PM10 frame with one physically-impossible reading."""
    stations = ["STA-01", "STA-02", "STA-03"]
    times = pd.date_range("2026-05-01", periods=60, freq="h")
    rows = []
    impossible_ts = times[30]
    for s in stations:
        for i, t in enumerate(times):
            value = 40.0 + 5.0 * np.sin(i / 6.0)
            if s == "STA-01" and t == impossible_ts:
                value = 5000.0  # far above the PM10 physical maximum → R07
            rows.append(
                {
                    C.STATION_ID: s,
                    C.PARAMETER: "PM10",
                    C.TIMESTAMP: t,
                    C.VALUE: value,
                    C.UNIT: "µg/m3",
                    C.SOURCE_FILE: f"{s}_air.csv",
                }
            )
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame = C.add_row_hash(frame)
    return C.validate(frame), impossible_ts


def test_rule_layer_overrides_ml_on_physical_impossibility(
    trained_models: dict[str, object],
) -> None:
    """The impossible reading is classified by rule even when the ML says otherwise."""
    deweather = trained_models["deweather"]
    fault = trained_models["fault"]
    adversarial = dataclasses.replace(fault, ml_model=_AdversarialModel())  # type: ignore[arg-type]

    frame, impossible_ts = _pm10_frame()
    out = classify_faults(frame, adversarial, deweather)  # type: ignore[arg-type]

    impossible = out[(out[C.STATION_ID] == "STA-01") & (out[C.TIMESTAMP] == impossible_ts)]
    assert impossible.iloc[0][FAULT_CLASS] == FaultClass.PHYSICALLY_IMPOSSIBLE.value
    assert impossible.iloc[0][SOURCE] == "rule"  # decided by rule, ML never consulted

    # A perfectly ordinary reading, by contrast, takes the adversarial model's vote —
    # proving the ML is genuinely in the loop and genuinely overridden above.
    ordinary = out[(out[C.STATION_ID] == "STA-02") & (out[SOURCE] == "ml")]
    assert not ordinary.empty
    assert set(ordinary[FAULT_CLASS]) == {FaultClass.CALIBRATION_DRIFT.value}
