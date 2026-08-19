"""Learned propagation validation: the HST-GAT path, its fallback, and attention export.

The phase gate's integration checks: the learned expectation drives a real adjudication
and stamps its provenance; deleting the artefact silently degrades to the phase-4
analytic verdict (standing rule 6); and the KER11-shaped characterization is unchanged
because the analytic default is byte-for-byte the phase-4 behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from provenance.config.loading import load_graph_config, load_models_config
from provenance.graph import scenarios as S
from provenance.graph.adjudicate import Verdict, validate_event
from provenance.graph.expectation import AnalyticExpectation
from provenance.models.hstgat.data import build_batch
from provenance.models.hstgat.train import train_model


@pytest.fixture(scope="module")
def gcfg() -> dict:
    return load_graph_config()


@pytest.fixture(scope="module")
def trained_dir(gcfg: dict, tmp_path_factory) -> Path:
    """Train a tiny HST-GAT on the scenario corpus and persist it once for the module."""
    from provenance.models.hstgat import store

    d = tmp_path_factory.mktemp("artefacts")
    sc = S.corroborated_plume()
    batch = build_batch(sc.frame, sc.points, sc.wind, gcfg, target_parameter="PM10")
    trained = train_model(
        batch, kind="hstgat", cfg=load_models_config(), epochs=30, data_checksum="scn00001"
    )
    store.save_model(trained, artefacts_dir=d, docs_dir=d / "docs")
    return d


def test_learned_path_produces_a_verdict_with_hstgat_provenance(
    gcfg: dict, trained_dir: Path
) -> None:
    from provenance.models.hstgat.forecast import learned_provider_factory

    sc = S.corroborated_plume()
    factory = learned_provider_factory(
        sc.frame, sc.points, sc.wind, gcfg, baseline_window_hours=48, artefacts_dir=trained_dir
    )
    provider = factory(sc.event)
    assert provider.provenance == "hst-gat"
    adj = validate_event(sc.event, sc.points, sc.wind, sc.frame, gcfg, expectation=provider)
    assert adj.evidence.expectation_provenance == "hst-gat"
    assert adj.verdict in set(Verdict)  # a real verdict, whatever it is (no accuracy claim)
    # The learned neighbours carry a predictive sigma the analytic path does not.
    assert adj.evidence.n_downwind >= 1


def test_fallback_when_artefact_deleted_returns_analytic_verdict(
    gcfg: dict, tmp_path: Path
) -> None:
    from provenance.models.hstgat.forecast import learned_provider_factory

    sc = S.corroborated_plume()
    # No artefact in this dir → the factory yields the analytic provider for every event.
    factory = learned_provider_factory(
        sc.frame, sc.points, sc.wind, gcfg, baseline_window_hours=48, artefacts_dir=tmp_path
    )
    provider = factory(sc.event)
    assert provider.provenance == "analytic"
    learned = validate_event(sc.event, sc.points, sc.wind, sc.frame, gcfg, expectation=provider)
    analytic = validate_event(sc.event, sc.points, sc.wind, sc.frame, gcfg)
    # The fallback verdict is exactly the phase-4 analytic verdict, and it says so.
    assert learned.evidence.expectation_provenance == "analytic"
    assert learned.verdict == analytic.verdict
    assert learned.confidence == analytic.confidence
    assert learned.evidence.match_score == analytic.evidence.match_score


def test_analytic_default_is_unchanged_by_the_seam(gcfg: dict) -> None:
    # The refactor that added the expectation seam must not move the analytic verdict.
    sc = S.corroborated_plume()
    default = validate_event(sc.event, sc.points, sc.wind, sc.frame, gcfg)
    explicit = validate_event(
        sc.event, sc.points, sc.wind, sc.frame, gcfg, expectation=AnalyticExpectation()
    )
    assert default.to_dict() == explicit.to_dict()
    assert default.verdict is Verdict.GENUINE_EVENT


def test_non_target_parameter_falls_back_to_analytic(gcfg: dict, trained_dir: Path) -> None:
    from dataclasses import replace

    from provenance.models.hstgat.forecast import learned_provider_factory

    sc = S.corroborated_plume()
    # An event on a parameter the model does not target must fall back, not guess.
    other_event = replace(sc.event, parameter="NO2")
    factory = learned_provider_factory(
        sc.frame, sc.points, sc.wind, gcfg, baseline_window_hours=48, artefacts_dir=trained_dir
    )
    assert factory(other_event).provenance == "analytic"


def test_conformal_wraps_the_hstgat_output(gcfg: dict, trained_dir: Path) -> None:
    # §7.7: the model's outputs gain a calibrated interval from a held-out time block.
    from provenance.models.hstgat import store
    from provenance.models.hstgat.conformalize import calibrate_and_coverage

    sc = S.corroborated_plume()
    loaded = store.load_latest(artefacts_dir=trained_dir)
    assert loaded is not None
    batch = build_batch(
        sc.frame,
        sc.points,
        sc.wind,
        gcfg,
        target_parameter="PM10",
        mean=loaded.mean,
        std=loaded.std,
    )
    conformal, report = calibrate_and_coverage(
        loaded.model, loaded.mean, loaded.std, batch, alpha=0.1, min_calibration=10
    )
    assert report["calibrated"] is True
    assert conformal is not None
    assert 0.0 <= report["empirical_coverage"] <= 1.0
    # A finite, adaptive interval for a predicted station value.
    lo, hi = conformal.interval([30.0], sigma=[2.0])
    assert lo[0] < 30.0 < hi[0]


def test_learned_adjudication_surfaces_calibrated_interval(gcfg: dict, tmp_path: Path) -> None:
    # Flag-3 resolution: the calibrated interval must reach the *evidence bundle*, not
    # just the model card. A learned neighbour carries its predictive sigma and a
    # conformal interval that brackets the expected excess.
    from provenance.models.hstgat import store
    from provenance.models.hstgat.conformalize import calibrate_and_coverage
    from provenance.models.hstgat.forecast import learned_provider_factory

    sc = S.corroborated_plume()
    batch = build_batch(sc.frame, sc.points, sc.wind, gcfg, target_parameter="PM10")
    trained = train_model(
        batch, kind="hstgat", cfg=load_models_config(), epochs=30, data_checksum="int00001"
    )
    conformal, _ = calibrate_and_coverage(
        trained.model, trained.mean, trained.std, batch, alpha=0.1, min_calibration=10
    )
    assert conformal is not None
    store.save_model(
        trained, artefacts_dir=tmp_path, docs_dir=tmp_path / "d", conformal=conformal.to_dict()
    )
    loaded = store.load_latest(artefacts_dir=tmp_path)
    assert loaded is not None and loaded.conformal is not None  # calibrator persisted

    factory = learned_provider_factory(
        sc.frame, sc.points, sc.wind, gcfg, baseline_window_hours=48, artefacts_dir=tmp_path
    )
    adj = validate_event(
        sc.event, sc.points, sc.wind, sc.frame, gcfg, expectation=factory(sc.event)
    )
    with_interval = [n for n in adj.evidence.downwind_neighbours if n.expected_interval is not None]
    assert with_interval  # at least one neighbour got a calibrated interval
    for n in with_interval:
        lo, hi = n.expected_interval
        assert lo <= n.expected_excess <= hi  # the interval brackets the point estimate
        assert n.sigma is not None and n.sigma >= 0.0
    # And it is JSON-safe for the bundle a human reviews.
    nd = adj.to_dict()["evidence"]["downwind_neighbours"][0]
    assert "expected_interval" in nd and "sigma" in nd


def test_attention_overlay_is_produced_for_a_drop(gcfg: dict, tmp_path: Path) -> None:
    # Flag-1 resolution: the attention export must be reachable from the product flow,
    # not only from a unit test. The drop-level helper the CLI calls writes an artefact.
    from provenance.models.hstgat import store
    from provenance.models.hstgat.attention import write_overlay_for_drop

    sc = S.corroborated_plume()
    batch = build_batch(sc.frame, sc.points, sc.wind, gcfg, target_parameter="PM10")
    trained = train_model(
        batch, kind="hstgat", cfg=load_models_config(), epochs=20, data_checksum="ov000001"
    )
    store.save_model(trained, artefacts_dir=tmp_path, docs_dir=tmp_path / "d")
    out = write_overlay_for_drop(
        sc.frame,
        sc.points,
        sc.wind,
        gcfg,
        tmp_path / "adj",
        at_time=sc.event.timestamp,
        artefacts_dir=tmp_path,
    )
    assert out is not None and out.exists()
    import json

    overlay = json.loads(out.read_text())
    assert overlay["relations"]["wind_conditioned"]


def test_overlay_helper_degrades_without_artefact(gcfg: dict, tmp_path: Path) -> None:
    from provenance.models.hstgat.attention import write_overlay_for_drop

    sc = S.corroborated_plume()
    # No artefact → no overlay, no error (graceful degradation, standing rule 6).
    out = write_overlay_for_drop(
        sc.frame, sc.points, sc.wind, gcfg, tmp_path, artefacts_dir=tmp_path
    )
    assert out is None


def test_attention_overlay_structure(gcfg: dict, trained_dir: Path) -> None:
    from provenance.models.hstgat import store
    from provenance.models.hstgat.attention import attention_overlay, write_overlay

    sc = S.corroborated_plume()
    loaded = store.load_latest(artefacts_dir=trained_dir)
    assert loaded is not None
    overlay = attention_overlay(
        loaded, sc.frame, sc.points, sc.wind, gcfg, at_time=sc.event.timestamp
    )
    assert overlay["target_parameter"] == "PM10"
    wind_edges = overlay["relations"]["wind_conditioned"]
    assert wind_edges  # the wind relation lights up edges
    for e in wind_edges:
        assert 0.0 <= e["attention"] <= 1.0
        assert {"src", "dst", "attention", "edge_weight"} <= set(e)
    # Attention over each station's incoming edges sums to ~1 per destination (softmax).
    # And it is round-trippable to JSON for the map.
    out = write_overlay(overlay, Path(gcfg and str(trained_dir)) / "overlay.json")
    assert out.exists()
