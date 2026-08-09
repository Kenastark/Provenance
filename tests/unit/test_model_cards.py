"""Model-card generation: the card is built from the model's own record.

A card must describe exactly the model it came from — the feature list, the CV scheme,
the metrics and the training-data checksum — so these assert the card reflects the model
rather than a hand-written approximation of it.
"""

from __future__ import annotations

import json

import pytest

from provenance.models.cards import deweather_card, fault_card, render_markdown

pytestmark = pytest.mark.unit


def test_deweather_card_reflects_the_model(trained_models: dict[str, object]) -> None:
    model = trained_models["deweather"]
    card = deweather_card(model)  # type: ignore[arg-type]
    assert card.name == "deweather"
    assert card.training_data_checksum == model.data_checksum  # type: ignore[attr-defined]
    assert card.stem == f"deweather-{model.version}"  # type: ignore[attr-defined]
    feature_names = {f["name"] for f in card.features}
    assert set(model.feature_names).issubset(feature_names)  # type: ignore[attr-defined]
    assert "forward-chaining" in card.cv_scheme
    # The integrity payload excludes the wall-clock timestamp (determinism).
    assert "generated_at" not in card.integrity_dict()


def test_fault_card_carries_confusion_and_floors(trained_models: dict[str, object]) -> None:
    model = trained_models["fault"]
    card = fault_card(model)  # type: ignore[arg-type]
    assert card.name == "fault"
    assert "confusion_matrix" in card.extra
    assert "recall_floors" in card.extra
    assert any("headline accuracy" in limit for limit in card.limitations)
    assert any("meteorological_artefact" in limit for limit in card.limitations)


def test_markdown_renders_all_sections(trained_models: dict[str, object]) -> None:
    card = deweather_card(trained_models["deweather"])  # type: ignore[arg-type]
    md = render_markdown(card)
    for heading in ("# Model card", "## Data", "## Features", "## Metrics", "## Known limitations"):
        assert heading in md
    assert card.training_data_checksum in md


def test_sidecar_json_is_deterministic(trained_models: dict[str, object]) -> None:
    card = fault_card(trained_models["fault"])  # type: ignore[arg-type]
    a = card.sidecar_json()
    b = card.sidecar_json()
    assert a == b  # sorted keys, no timestamp in the integrity payload
    json.loads(a)  # valid JSON
