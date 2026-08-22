"""The imputation model's serving-side pieces (§7.2): normalisation, the trust
component's modelled/placeholder split, and graceful degradation when no artefact
exists for a parameter."""

from __future__ import annotations

import math

import pandas as pd
import pytest
from tests.support import series_rows

from provenance.grid.coverage import build_coverage
from provenance.models.hstgat.imputation_serving import (
    available_imputation_models,
    sigma_to_uncertainty,
)
from provenance.schema import canonical as C
from provenance.trust import components as comp
from provenance.trust.weights import load_trust_weights

_CLEAN = [30.0 + 10.0 * math.sin(2 * math.pi * i / 12) for i in range(48)]


def _frame(specs: list[tuple[str, list[float]]]) -> pd.DataFrame:
    rows: list[dict] = []
    for station, values in specs:
        rows += series_rows(station, "PM10", values)
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    return C.validate(C.add_row_hash(frame))


class TestSigmaToUncertainty:
    def test_zero_sigma_is_zero_uncertainty(self) -> None:
        assert sigma_to_uncertainty(0.0) == 0.0

    def test_bounded_in_zero_one(self) -> None:
        # tanh saturates to exactly 1.0 in float64 for a large enough input; the
        # contract is "never exceeds 1", not "never reaches it in the limit".
        for sigma in (0.1, 1.0, 5.0, 1000.0):
            u = sigma_to_uncertainty(sigma)
            assert 0.0 <= u <= 1.0

    def test_monotonic(self) -> None:
        values = [sigma_to_uncertainty(s) for s in (0.0, 0.2, 0.5, 1.0, 2.0, 10.0)]
        assert values == sorted(values)
        assert len(set(values)) == len(values)  # strictly increasing


class TestAvailableImputationModels:
    def test_no_artefacts_dir_degrades_to_empty(self, tmp_path) -> None:
        # An empty/nonexistent store is a normal state (standing rule 6), not an error.
        out = available_imputation_models(
            ["PM10", "NO2"], data_checksum="anything", artefacts_dir=tmp_path
        )
        assert out == {}

    def test_artefact_from_a_different_drop_is_not_used(self, tmp_path) -> None:
        """A real bug, not a hypothetical: the artefact store keeps one file per
        parameter name regardless of which corpus trained it. Without this check, a
        model trained on drop A silently runs inference against drop B whenever they
        share a parameter name (e.g. the real Green Sentinel drop and the synthetic
        demo corpus both carry "PM10") - a station graph the model never saw,
        producing a plausible-looking but meaningless number. This is what actually
        happened during this update's own verification (the synthetic demo corpus's
        Trust Scores changed after training real-drop imputation models locally)."""
        from provenance.config.loading import load_graph_config, load_models_config
        from provenance.fixtures.generator import write_corpus
        from provenance.graph.build import station_points_from_metadata
        from provenance.graph.wind import WindField
        from provenance.io import loaders
        from provenance.models.hstgat import store
        from provenance.models.hstgat.data import build_batch
        from provenance.models.hstgat.train import train_model
        from provenance.schema.observe import observe

        source = tmp_path / "drop"
        write_corpus(source, seed=1, n_days=14, n_stations=4)
        frame = loaders.load_data(source)
        meta = loaders.load_station_metadata(source)
        points = station_points_from_metadata(dict(meta))
        gcfg = load_graph_config()
        mcfg = load_models_config()
        wind = WindField.from_frame(frame)
        batch = build_batch(frame, points, wind, gcfg, target_parameter="PM10")
        checksum = observe(frame).checksum
        trained = train_model(
            batch,
            kind="hstgat",
            cfg=mcfg,
            epochs=1,
            data_checksum=checksum,
            artefact_name="imputation-PM10",
        )
        art = tmp_path / "art"
        store.save_model(trained, artefacts_dir=art, docs_dir=tmp_path / "docs")

        # The exact checksum this artefact was trained on: used.
        matching = available_imputation_models(["PM10"], data_checksum=checksum, artefacts_dir=art)
        assert "PM10" in matching

        # A different drop's checksum, same parameter name: not used.
        mismatched = available_imputation_models(
            ["PM10"], data_checksum="a-completely-different-drop-checksum", artefacts_dir=art
        )
        assert mismatched == {}


class TestImputationUncertaintyComponent:
    def _args(self, frame: pd.DataFrame, station: str):
        coverage = build_coverage(frame)
        at = pd.Timestamp(frame[C.TIMESTAMP].max())
        cfg = load_trust_weights()
        return coverage, station, at, cfg

    def test_no_model_keeps_placeholder_behaviour(self) -> None:
        frame = _frame([("S1", _CLEAN[:24] + [float("nan")] * 24), ("S2", _CLEAN)])
        coverage, station, at, cfg = self._args(frame, "S1")
        result, codes, _notes = comp.imputation_uncertainty(coverage, station, at, cfg)
        assert result.is_placeholder is True
        assert "modelled_pct" not in result.evidence
        assert "pct" in result.evidence
        if result.evidence["pct"] > 0:
            assert codes == ["T02"]

    def test_modelled_value_drives_component_and_keeps_raw_figure(self) -> None:
        frame = _frame([("S1", _CLEAN[:24] + [float("nan")] * 24), ("S2", _CLEAN)])
        coverage, station, at, cfg = self._args(frame, "S1")
        result, codes, notes = comp.imputation_uncertainty(coverage, station, at, cfg, modelled=0.3)
        assert result.is_placeholder is False
        assert result.value == pytest.approx(0.7)  # certainty = 1 - modelled
        assert result.evidence["modelled_pct"] == 30.0
        assert "pct" in result.evidence  # raw absent fraction still reported
        assert codes == ["T06"]
        assert any("modelled" in n for n in notes)

    def test_modelled_value_is_clamped_to_unit_interval(self) -> None:
        frame = _frame([("S1", _CLEAN), ("S2", _CLEAN)])
        coverage, station, at, cfg = self._args(frame, "S1")
        result, _codes, _notes = comp.imputation_uncertainty(
            coverage, station, at, cfg, modelled=1.7
        )
        assert result.evidence["modelled_pct"] == 100.0
        assert result.value == pytest.approx(0.0)
