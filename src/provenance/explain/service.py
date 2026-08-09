"""Explain one defect: SHAP when a model can speak, the rule reason when it cannot.

This is the pure core behind ``GET /v1/explain/{defect_id}``. Given the readings for a
station, the defect's coordinates, and a loaded model bundle (or ``None``), it returns
a single explanation object. The API layer does the database access and serialisation;
everything here is a function of its arguments, so it is testable without a server.

Three outcomes, all honest:

* **model** — the defect's pollutant is covered by the deweather model, so the
  weather-predicted value is explained with SHAP and the residual and fault class are
  reported alongside.
* **rule** — the defect's parameter is not model-covered (or the reading is not
  present), so the deterministic reason code is the explanation.
* **degraded** — no model artefact was available. The statistics-layer reason is
  returned and the response is flagged degraded (standing rule 6), never dressed up as
  a model explanation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from provenance.config import reason_codes
from provenance.explain.render import operator_sentence
from provenance.explain.shap_explain import ShapExplanation, explain_deweather
from provenance.models.deweather.model import RESIDUAL
from provenance.models.features import build_features
from provenance.schema import canonical as C


@dataclass(frozen=True, slots=True)
class DefectRef:
    """The coordinates of the defect being explained."""

    defect_id: int
    station_id: str
    parameter: str
    timestamp_utc: pd.Timestamp
    reason_code: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    """The explanation, ready for the API to serialise."""

    ref: DefectRef
    method: str  # "model" | "rule" | "degraded"
    sentence: str
    degraded: bool
    model_versions: dict[str, str]
    fault_class: str | None = None
    shap: ShapExplanation | None = None
    residual: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "defect_id": self.ref.defect_id,
            "station_id": self.ref.station_id,
            "parameter": self.ref.parameter,
            "timestamp_utc": pd.Timestamp(self.ref.timestamp_utc).isoformat(),
            "reason_code": self.ref.reason_code,
            "method": self.method,
            "fault_class": self.fault_class,
            "sentence": self.sentence,
            "degraded": self.degraded,
            "model_versions": dict(self.model_versions),
            "residual": None if self.residual is None else round(self.residual, 4),
            "notes": list(self.notes),
            "attributions": [],
            "base_value": None,
            "prediction": None,
            "predicted_class": None,
            "reconstructs": None,
        }
        if self.shap is not None:
            d["attributions"] = [a.to_dict() for a in self.shap.attributions]
            d["base_value"] = round(self.shap.base_value, 6)
            d["prediction"] = round(self.shap.prediction, 6)
            d["predicted_class"] = self.shap.predicted_class
            d["reconstructs"] = self.shap.reconstructs()
        return d


def _reason_sentence(ref: DefectRef) -> str:
    # The reason-code sentence templates reference {parameter} (and sometimes the
    # station), which live in their own columns, not the evidence dict — merge them in
    # so the sentence renders with figures rather than raw placeholders.
    substitutions = {
        "parameter": ref.parameter,
        "station": ref.station_id,
        "station_id": ref.station_id,
        **ref.evidence,
    }
    try:
        return reason_codes.get(ref.reason_code).render(**substitutions)
    except KeyError:
        return "This reading was flagged by the statistics layer."


def explain_defect(
    frame: pd.DataFrame,
    ref: DefectRef,
    bundle: Any | None,
    *,
    weather: pd.DataFrame | None = None,
    top_k: int = 3,
) -> ExplanationResult:
    """Explain a single defect. ``bundle`` is a loaded ModelBundle or ``None``.

    ``None`` means no model artefact was available: the result is the statistics-layer
    reason, flagged degraded. That is the graceful-degradation path the demo depends on.
    """
    if bundle is None:
        return ExplanationResult(
            ref=ref,
            method="degraded",
            sentence=_reason_sentence(ref),
            degraded=True,
            model_versions={},
            notes=[
                "No model artefact was available; this explanation comes from the "
                "statistics layer alone (standing rule 6). Train models with "
                "`prov models train` to enable SHAP attributions.",
            ],
        )

    deweather = bundle.deweather
    fault = bundle.fault
    versions = bundle.versions

    # Fault class from the hybrid classifier (rules first), for context on any cell.
    fault_class = _fault_class_for(frame, ref, bundle, weather)

    if ref.parameter not in deweather.regressors or frame.empty:
        return ExplanationResult(
            ref=ref,
            method="rule",
            sentence=_reason_sentence(ref),
            degraded=False,
            model_versions=versions,
            fault_class=fault_class,
            notes=[
                f"{ref.parameter} is not covered by the deweather model "
                f"({', '.join(deweather.pollutants)}); the deterministic reason is shown.",
            ],
        )

    matrix, _ = build_features(frame, weather=weather)
    key = (ref.station_id, pd.Timestamp(ref.timestamp_utc))
    if key not in matrix.index:
        return ExplanationResult(
            ref=ref,
            method="rule",
            sentence=_reason_sentence(ref),
            degraded=False,
            model_versions=versions,
            fault_class=fault_class,
            notes=["No feature row for this cell; the deterministic reason is shown."],
        )

    feature_row = matrix.loc[key]  # type: ignore[index]
    shap_exp = explain_deweather(deweather, ref.parameter, feature_row)
    residual = _residual_for(deweather, frame, ref, weather)
    sentence = operator_sentence(shap_exp, top_k=top_k)
    return ExplanationResult(
        ref=ref,
        method="model",
        sentence=sentence,
        degraded=False,
        model_versions=versions,
        fault_class=fault_class,
        shap=shap_exp,
        residual=residual,
        notes=[fault.notes[0]] if fault.notes else [],
    )


def _fault_class_for(
    frame: pd.DataFrame, ref: DefectRef, bundle: Any, weather: pd.DataFrame | None
) -> str | None:
    from provenance.models.fault import classify_faults

    if frame.empty:
        return None
    out = classify_faults(frame, bundle.fault, bundle.deweather, weather=weather)
    match = out[
        (out[C.STATION_ID] == ref.station_id)
        & (out[C.PARAMETER] == ref.parameter)
        & (out[C.TIMESTAMP] == pd.Timestamp(ref.timestamp_utc))
    ]
    if match.empty:
        return None
    return str(match.iloc[0]["fault_class"])


def _residual_for(
    deweather: Any, frame: pd.DataFrame, ref: DefectRef, weather: pd.DataFrame | None
) -> float | None:
    residuals = deweather.predict_series(frame, weather=weather)
    match = residuals[
        (residuals[C.STATION_ID] == ref.station_id)
        & (residuals[C.PARAMETER] == ref.parameter)
        & (residuals[C.TIMESTAMP] == pd.Timestamp(ref.timestamp_utc))
    ]
    if match.empty:
        return None
    return float(match.iloc[0][RESIDUAL])
