"""Registry tests: a model without a card must not load, and absence degrades.

Two guarantees are pinned here. First, ``load_artefact`` refuses an artefact whose card
sidecar is missing or whose checksum disagrees — a model whose provenance cannot be
verified never loads (§5). Second, an empty store yields ``None`` from ``load_bundle``
rather than raising, which is the graceful-degradation contract the demo depends on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from provenance.models import registry
from provenance.models.registry import ModelCardMissingError

pytestmark = pytest.mark.unit


@pytest.fixture
def saved_store(trained_models: dict[str, object], tmp_path: Path) -> Path:
    art = tmp_path / "art"
    docs = tmp_path / "docs"
    registry.save_model(trained_models["deweather"], artefacts_dir=art, docs_dir=docs)  # type: ignore[arg-type]
    registry.save_model(trained_models["fault"], artefacts_dir=art, docs_dir=docs)  # type: ignore[arg-type]
    return art


def test_save_then_load_bundle_round_trips(
    saved_store: Path, trained_models: dict[str, object]
) -> None:
    assert registry.bundle_available(saved_store)
    bundle = registry.load_bundle(saved_store)
    assert bundle is not None
    assert bundle.deweather.version == trained_models["deweather"].version  # type: ignore[attr-defined]
    assert bundle.fault.version == trained_models["fault"].version  # type: ignore[attr-defined]


def test_missing_card_refuses_to_load(saved_store: Path) -> None:
    stem = registry.latest_stem("deweather", artefacts_dir=saved_store)
    assert stem is not None
    (saved_store / f"{stem}.card.json").unlink()
    assert not registry.bundle_available(saved_store)
    with pytest.raises(ModelCardMissingError, match="no card sidecar"):
        registry.load_artefact(stem, artefacts_dir=saved_store)


def test_mismatched_card_checksum_refuses_to_load(saved_store: Path) -> None:
    stem = registry.latest_stem("fault", artefacts_dir=saved_store)
    assert stem is not None
    card_path = saved_store / f"{stem}.card.json"
    data = json.loads(card_path.read_text())
    data["training_data_checksum"] = "tampered"
    card_path.write_text(json.dumps(data))
    with pytest.raises(ModelCardMissingError, match="does not match"):
        registry.load_artefact(stem, artefacts_dir=saved_store)


def test_empty_store_degrades_to_none(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    assert registry.load_bundle(empty) is None  # graceful degradation, never raises
    assert not registry.bundle_available(empty)
