"""Ingestion adapters and the registry that resolves a source to its adapter.

The registry is the single place that knows the set of sources. A new adapter — a
Kafka consumer, say — is added here and nowhere else; detectors, audit, and trust
never learn a source's name. ``resolve`` picks an adapter by key; ``discover``
finds which adapters have data under a root.
"""

from __future__ import annotations

from pathlib import Path

from provenance.io.ingest.base import IngestAdapter, SourceNotReady
from provenance.io.ingest.enclod import EnclodAdapter
from provenance.io.ingest.green_sentinel import GreenSentinelAdapter
from provenance.io.ingest.gtfs import GtfsAdapter
from provenance.io.ingest.hungaromet import HungaroMetAdapter

_ADAPTERS: dict[str, IngestAdapter] = {
    a.source: a
    for a in (
        GreenSentinelAdapter(),
        EnclodAdapter(),
        HungaroMetAdapter(),
        GtfsAdapter(),
    )
}


def available_sources() -> list[str]:
    """Every source key the system knows how to ingest."""
    return sorted(_ADAPTERS)


def resolve(source: str) -> IngestAdapter:
    """Return the adapter for ``source``, or raise a helpful error."""
    try:
        return _ADAPTERS[source]
    except KeyError:
        known = ", ".join(available_sources())
        raise KeyError(f"Unknown ingest source {source!r}. Known sources: {known}") from None


def discover(root: Path) -> dict[str, list[Path]]:
    """Map each source to the files it recognises under ``root`` (non-empty only)."""
    found: dict[str, list[Path]] = {}
    for source, adapter in _ADAPTERS.items():
        files = adapter.discover(Path(root))
        if files:
            found[source] = files
    return found


__all__ = [
    "EnclodAdapter",
    "GreenSentinelAdapter",
    "GtfsAdapter",
    "HungaroMetAdapter",
    "IngestAdapter",
    "SourceNotReady",
    "available_sources",
    "discover",
    "resolve",
]
