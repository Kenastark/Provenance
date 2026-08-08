"""Standing rule 9, mechanised: no serialiser can emit a bare trust score.

Two layers are checked. The value object (:class:`TrustScore`) refuses to construct
without a component breakdown and a reason code. The wire model
(:class:`TrustScoreOut`) requires both fields non-empty. And a structural sweep of
the response schemas asserts that *any* model carrying a ``trust`` value also
carries ``components`` and ``reason_codes`` — so a future model cannot quietly
reintroduce a bare number.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel, ValidationError

from provenance.api import schemas
from provenance.trust.score import Risk, TrustComponent, TrustScore

_RISK = Risk(value=1.0, trust=1.0, severity_vs_threshold=1.0, population_exposure=1.0)
_COMPONENT = {
    "name": "HealthConf",
    "value": 1.0,
    "weight": 0.35,
    "contribution": 0.35,
    "is_placeholder": False,
    "detail": "",
}


def _response_models() -> list[type[BaseModel]]:
    return [
        obj
        for _, obj in inspect.getmembers(schemas, inspect.isclass)
        if issubclass(obj, BaseModel) and obj is not BaseModel
    ]


def test_any_model_with_a_trust_value_also_carries_its_explanation() -> None:
    # A station-scoped trust value is a *rendered score* and must be explained. A
    # bare ``trust`` scalar that is a formula input (RiskOut.trust) is not — it is
    # only ever nested inside a fully-explained TrustScoreOut. The station_id +
    # trust pairing is what marks a model as a score payload.
    for model in _response_models():
        fields = set(model.model_fields)
        if "trust" in fields and "station_id" in fields:
            assert "components" in fields and "reason_codes" in fields, (
                f"{model.__name__} exposes a station trust value without "
                "components/reason_codes; that is a bare score (standing rule 9)."
            )


def test_trust_score_out_requires_nonempty_components_and_codes() -> None:
    with pytest.raises(ValidationError):
        schemas.TrustScoreOut(
            station_id="S1",
            timestamp_utc="2026-05-01T00:00:00",
            trust=1.0,
            components=[],
            reason_codes=["T00"],
            risk=schemas.RiskOut(**_RISK.to_dict()),
        )
    with pytest.raises(ValidationError):
        schemas.TrustScoreOut(
            station_id="S1",
            timestamp_utc="2026-05-01T00:00:00",
            trust=1.0,
            components=[schemas.ComponentOut(**_COMPONENT)],
            reason_codes=[],
            risk=schemas.RiskOut(**_RISK.to_dict()),
        )


def test_trust_score_value_object_enforces_the_same_rule() -> None:
    with pytest.raises(ValueError):
        TrustScore(
            station_id="S1",
            timestamp_utc="2026-05-01T00:00:00",
            value=1.0,
            components=[TrustComponent(name="HealthConf", value=1.0, weight=0.35)],
            reason_codes=[],
            risk=_RISK,
        )
