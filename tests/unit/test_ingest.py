"""The ingestion abstraction: discovery, resolution, and loud failure on unconfirmed
sources. Adding a source is a change here and nowhere downstream."""

from __future__ import annotations

from pathlib import Path

import pytest

from provenance.config.loading import load_schema_assumptions
from provenance.fixtures.enclod import write_enclod_bundle
from provenance.io import ingest
from provenance.io.ingest import (
    EnclodAdapter,
    GreenSentinelAdapter,
    GtfsAdapter,
    HungaroMetAdapter,
    SourceNotReady,
)
from provenance.io.ingest.base import IngestAdapter
from provenance.io.ingest.enclod import counter_locations
from provenance.schema.canonical import SchemaDriftError


def test_all_adapters_satisfy_the_protocol() -> None:
    for source in ingest.available_sources():
        assert isinstance(ingest.resolve(source), IngestAdapter)


def test_resolve_unknown_source_is_a_useful_error() -> None:
    with pytest.raises(KeyError, match="Known sources"):
        ingest.resolve("kafka")


def test_green_sentinel_adapter_reads_the_fixture_corpus() -> None:
    adapter = GreenSentinelAdapter()
    root = Path("tests/fixtures")
    assert adapter.discover(root)  # finds corpus.parquet
    frame = adapter.read(root)
    assert len(frame) > 0
    assert frame["station_id"].nunique() >= 1


def test_discover_maps_sources_to_files(tmp_path: Path) -> None:
    (tmp_path / "stops.txt").write_text("stop_id\n")
    found = ingest.discover(tmp_path)
    assert "gtfs" in found


def test_enclod_fails_loudly_while_columns_are_unconfirmed(tmp_path: Path) -> None:
    with pytest.raises(SchemaDriftError, match="unconfirmed"):
        EnclodAdapter().read(tmp_path)


def test_observing_enclod_columns_does_not_open_the_parse_gate() -> None:
    """Writing the real column names down is not the same as being able to parse.

    ADR 0005 records the observed wide schema and the canonical mapping, which
    moves `enclod_traffic.status` to `observed`. Only `confirmed` may open the
    gate, and promoting it is the same change that implements the parse — so a
    config edit on its own must never route callers into unwritten code.
    """
    cfg = load_schema_assumptions()["enclod_traffic"]
    assert cfg["status"] == "observed"
    assert cfg["measure_columns"], "the observed wide schema must be recorded"
    assert cfg["counter_id_column"] == "uuid"
    with pytest.raises(SchemaDriftError):
        EnclodAdapter().read(Path())


def test_counter_locations_raises_source_not_ready_with_no_bundle(tmp_path: Path) -> None:
    with pytest.raises(SourceNotReady):
        counter_locations(tmp_path)


def test_counter_locations_reads_real_coordinates_without_opening_the_parse_gate(
    tmp_path: Path,
) -> None:
    """Coordinates are observed columns (ADR 0005), independent of the cumulative
    counter parse that ``EnclodAdapter.read`` still refuses."""
    write_enclod_bundle(tmp_path, {"C1": (47.53, 21.63), "C2": (47.56, 21.68)})
    locations = counter_locations(tmp_path)

    assert sorted(locations["counter_id"]) == ["C1", "C2"]
    row = locations.set_index("counter_id").loc["C1"]
    assert row["lat"] == pytest.approx(47.53)
    assert row["lon"] == pytest.approx(21.63)
    assert row["name"] == "counter.C1"
    # The full canonical parse is still gated - reading a coordinate commits to
    # nothing about the reset-aware differencing.
    with pytest.raises(SchemaDriftError):
        EnclodAdapter().read(tmp_path)


def test_weather_and_gtfs_report_not_ready(tmp_path: Path) -> None:
    with pytest.raises(SourceNotReady):
        HungaroMetAdapter().read(tmp_path)
    with pytest.raises(SourceNotReady):
        GtfsAdapter().read(tmp_path)


def test_adapters_declare_a_kind() -> None:
    kinds = {ingest.resolve(s).kind for s in ingest.available_sources()}
    assert kinds <= {"readings", "covariate", "reference"}
    assert GreenSentinelAdapter().kind == "readings"
