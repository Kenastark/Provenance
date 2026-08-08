"""The ingestion abstraction: discovery, resolution, and loud failure on unconfirmed
sources. Adding a source is a change here and nowhere downstream."""

from __future__ import annotations

from pathlib import Path

import pytest

from provenance.io import ingest
from provenance.io.ingest import (
    EnclodAdapter,
    GreenSentinelAdapter,
    GtfsAdapter,
    HungaroMetAdapter,
    SourceNotReady,
)
from provenance.io.ingest.base import IngestAdapter
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


def test_weather_and_gtfs_report_not_ready(tmp_path: Path) -> None:
    with pytest.raises(SourceNotReady):
        HungaroMetAdapter().read(tmp_path)
    with pytest.raises(SourceNotReady):
        GtfsAdapter().read(tmp_path)


def test_adapters_declare_a_kind() -> None:
    kinds = {ingest.resolve(s).kind for s in ingest.available_sources()}
    assert kinds <= {"readings", "covariate", "reference"}
    assert GreenSentinelAdapter().kind == "readings"
