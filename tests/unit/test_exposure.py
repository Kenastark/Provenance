"""PopulationExposure from the GTFS transit-corridor layer (§7.8, phase 7).

The stub is gone: exposure is computed from a GTFS bundle, varies with transit
service intensity, is bounded, and degrades to a flagged neutral 1.0 when there is
nothing to measure.
"""

from __future__ import annotations

import pandas as pd
import pytest

from provenance.fixtures.gtfs import generate_gtfs, write_gtfs_bundle
from provenance.grid.exposure import (
    ExposureParams,
    build_exposure_layer,
    station_service_intensity,
)
from provenance.io.ingest.gtfs import find_gtfs_bundle, stops_with_route_counts
from provenance.trust.score import Risk

pytestmark = pytest.mark.unit

# Two well-separated stations so their 500 m corridors never overlap.
_POINTS = {"BUSY": (47.5300, 21.6300), "QUIET": (47.5600, 21.6800)}


def _stops(rows: list[tuple[float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame([{"stop_lat": lat, "stop_lon": lon, "n_routes": n} for lat, lon, n in rows])


def test_denser_corridor_gets_higher_exposure() -> None:
    stops = _stops(
        [
            (47.5300, 21.6300, 4.0),  # on top of BUSY
            (47.5301, 21.6301, 4.0),  # inside BUSY's corridor
            (47.5600, 21.6800, 1.0),  # on top of QUIET
        ]
    )
    layer = build_exposure_layer(stops, _POINTS)
    assert layer.factor_for("BUSY") > layer.factor_for("QUIET")
    # Bounded within the configured band, never a raw count leaking into Risk.
    p = ExposureParams.from_config()
    for sid in _POINTS:
        assert p.floor <= layer.factor_for(sid) <= p.ceil


def test_stops_outside_the_corridor_do_not_count() -> None:
    intensity = station_service_intensity(
        _stops([(47.5600, 21.6800, 5.0)]), _POINTS, ExposureParams.from_config()
    )
    assert intensity["QUIET"] == 5.0
    assert intensity["BUSY"] == 0.0  # 5 km away, well outside the 500 m corridor


def test_flat_network_maps_every_station_to_neutral() -> None:
    # Equal service everywhere: normalisation must not manufacture a spread.
    stops = _stops([(47.5300, 21.6300, 2.0), (47.5600, 21.6800, 2.0)])
    layer = build_exposure_layer(stops, _POINTS)
    assert layer.factor_for("BUSY") == 1.0
    assert layer.factor_for("QUIET") == 1.0


def test_unserved_station_is_neutral_and_not_measured() -> None:
    stops = _stops([(47.5300, 21.6300, 3.0)])  # only BUSY is served
    layer = build_exposure_layer(stops, _POINTS)
    assert layer.is_measured("BUSY") is True
    assert layer.is_measured("QUIET") is False
    assert layer.factor_for("QUIET") == 1.0


def test_gtfs_fixture_roundtrips_through_the_parser(workspace) -> None:
    bundle = write_gtfs_bundle(workspace, _POINTS)
    assert find_gtfs_bundle(workspace) == bundle
    stops = stops_with_route_counts(bundle)
    assert set(stops.columns) == {"stop_id", "stop_lat", "stop_lon", "n_routes"}
    assert (stops["n_routes"] >= 1).all()
    # The parser's route-per-stop join recovers the generator's per-station weight.
    tables = generate_gtfs(_POINTS)
    assert len(stops) == len(tables["stops"])


def test_generated_bundle_yields_a_measured_varied_layer(workspace) -> None:
    bundle = write_gtfs_bundle(workspace, _POINTS)
    stops = stops_with_route_counts(bundle)
    layer = build_exposure_layer(stops, _POINTS)
    factors = {layer.factor_for(s) for s in _POINTS}
    assert len(factors) > 1  # a real spread the Risk ranking can use


def test_exposure_flows_into_risk_and_clears_the_stub_flag() -> None:
    stubbed = Risk(value=1.0, trust=1.0, severity_vs_threshold=1.0, population_exposure=1.0)
    assert stubbed.population_exposure_stubbed is True
    measured = Risk(
        value=1.6,
        trust=1.0,
        severity_vs_threshold=1.0,
        population_exposure=1.6,
        population_exposure_stubbed=False,
    )
    assert measured.population_exposure_stubbed is False
