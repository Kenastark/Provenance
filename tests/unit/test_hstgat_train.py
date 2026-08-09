"""Training reproducibility, manifests, and the artefact store's card discipline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from provenance.config.loading import config_hash, load_graph_config, load_models_config
from provenance.graph import scenarios as S
from provenance.models.hstgat.data import build_batch, truncate_batch
from provenance.models.hstgat.train import train_model, write_manifest
from provenance.models.registry import ModelCardMissingError


@pytest.fixture(scope="module")
def batch():
    sc = S.corroborated_plume()
    full = build_batch(sc.frame, sc.points, sc.wind, load_graph_config(), target_parameter="PM10")
    return truncate_batch(full, 12)


@pytest.fixture(scope="module")
def mcfg() -> dict:
    return load_models_config()


def test_two_trainings_are_byte_identical(batch, mcfg: dict) -> None:
    a = train_model(batch, kind="hstgat", cfg=mcfg, epochs=15, data_checksum="abc")
    b = train_model(batch, kind="hstgat", cfg=mcfg, epochs=15, data_checksum="abc")
    for pa, pb in zip(a.model.parameters(), b.model.parameters(), strict=True):
        assert torch.equal(pa, pb)  # determinism (standing rule 8)
    assert a.metrics == b.metrics


def test_manifest_records_provenance(batch, mcfg: dict, tmp_path: Path) -> None:
    trained = train_model(batch, kind="hstgat", cfg=mcfg, epochs=5, data_checksum="feed0000")
    path = write_manifest(trained, config_hash(), tmp_path)
    manifest = json.loads(path.read_text())
    # Seed, config hash, data checksum, git sha, metrics and the parameter count (§ brief).
    assert manifest["seed"] == trained.seed
    assert manifest["data_checksum"] == "feed0000"
    assert manifest["parameter_count"] == trained.parameter_count
    assert "git_sha" in manifest and "metrics" in manifest
    assert manifest["config_hash"] == config_hash()


def test_metrics_have_no_accuracy_or_f1(batch, mcfg: dict) -> None:
    # Standing rule 4: the model reports reconstruction metrics, never a propagation
    # accuracy or F1.
    trained = train_model(batch, kind="hstgat", cfg=mcfg, epochs=5, data_checksum="x")
    keys = " ".join(trained.metrics).lower()
    assert "accuracy" not in keys and "f1" not in keys


def test_gcn_baseline_trains(batch, mcfg: dict) -> None:
    trained = train_model(batch, kind="gcn", cfg=mcfg, epochs=5, data_checksum="base0001")
    assert trained.kind == "gcn"
    assert trained.name == "gcn"
    assert trained.parameter_count > 0


def test_save_load_roundtrip_and_card(batch, mcfg: dict, tmp_path: Path) -> None:
    from provenance.models.hstgat import store

    trained = train_model(batch, kind="hstgat", cfg=mcfg, epochs=5, data_checksum="cafe0001")
    paths = store.save_model(
        trained, config_hash="h", artefacts_dir=tmp_path, docs_dir=tmp_path / "d"
    )
    assert paths["model"].name == "hst-gat-v1-cafe0001.pt"
    loaded = store.load_latest(artefacts_dir=tmp_path)
    assert loaded is not None
    assert loaded.target_parameter == "PM10"
    assert loaded.model.parameter_count() == trained.parameter_count
    # Reloaded weights match the trained ones.
    for name, p in trained.model.state_dict().items():
        assert torch.equal(loaded.model.state_dict()[name], p)


def test_missing_artefact_returns_none(tmp_path: Path) -> None:
    from provenance.models.hstgat import store

    # Graceful degradation: no artefact is a normal state, not an error.
    assert store.load_latest(artefacts_dir=tmp_path) is None


def test_artefact_without_card_refuses_to_load(batch, mcfg: dict, tmp_path: Path) -> None:
    from provenance.models.hstgat import store

    trained = train_model(batch, kind="hstgat", cfg=mcfg, epochs=3, data_checksum="cafe0002")
    store.save_model(trained, artefacts_dir=tmp_path, docs_dir=tmp_path / "d")
    (tmp_path / "hst-gat-v1-cafe0002.card.json").unlink()
    with pytest.raises(ModelCardMissingError):
        store.load_latest(artefacts_dir=tmp_path)


def test_card_checksum_mismatch_refuses_to_load(batch, mcfg: dict, tmp_path: Path) -> None:
    from provenance.models.hstgat import store

    trained = train_model(batch, kind="hstgat", cfg=mcfg, epochs=3, data_checksum="cafe0003")
    store.save_model(trained, artefacts_dir=tmp_path, docs_dir=tmp_path / "d")
    card_path = tmp_path / "hst-gat-v1-cafe0003.card.json"
    card = json.loads(card_path.read_text())
    card["training_data_checksum"] = "tampered"
    card_path.write_text(json.dumps(card))
    with pytest.raises(ModelCardMissingError, match="does not match"):
        store.load_latest(artefacts_dir=tmp_path)
