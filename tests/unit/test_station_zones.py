"""The curated, provisional station→zone map.

zone_type has no source in the Green Sentinel export, so it is human-curated in
config/station_zones.yaml. These tests guard the shape and honesty of that config
(every zone is a declared category; the file declares itself provisional), not the
correctness of any individual classification — which is a human judgement pending
expert sign-off.
"""

from __future__ import annotations

import yaml

from provenance.config.loading import STATION_ZONES_PATH, load_station_zones


def _raw() -> dict:
    return yaml.safe_load(STATION_ZONES_PATH.read_text(encoding="utf-8"))


def test_zone_map_covers_the_sixteen_land_stations() -> None:
    zones = load_station_zones()
    assert len(zones) == 16
    assert all(sid.startswith("DEB-KER") for sid in zones)


def test_every_zone_is_a_declared_category() -> None:
    data = _raw()
    categories = set(data["categories"])
    zones = load_station_zones()
    assert zones.values()  # non-empty
    assert set(zones.values()) <= categories


def test_the_map_declares_itself_provisional_with_rationale() -> None:
    # The classification is curated, not measured; it must say so and justify each row.
    data = _raw()
    assert data["status"] == "provisional"
    for sid, spec in data["stations"].items():
        assert spec["rationale"].strip(), f"{sid} has no rationale"
        assert spec["confidence"] in {"low", "medium", "high"}


def test_fixture_stations_are_absent_so_they_stay_null() -> None:
    # The synthetic STA-* stations are not in the curated map, so the loader leaves
    # their zone_type null rather than inventing one.
    zones = load_station_zones()
    assert "STA-01" not in zones
