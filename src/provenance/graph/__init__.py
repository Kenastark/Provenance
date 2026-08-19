"""Heterogeneous graph construction, wind-conditioned edges, and adjudication (phase 4).

The public surface, in pipeline order:

* :class:`~provenance.graph.snapshot.GraphSnapshot` — the whole graph at one instant,
  node/edge tables over numpy today, the seam PyG backs in phase 6.
* :func:`~provenance.graph.build.build_snapshot` — assemble one from stations + wind.
* :func:`~provenance.graph.adjudicate.validate_event` — the propagation adjudicator,
  returning a :class:`~provenance.graph.adjudicate.Verdict` with a full evidence bundle.
* :mod:`~provenance.graph.replay` — rank the corpus's events and adjudicate each.

Nothing here imports the presentation layers (``api``/``report``) or the downstream
neural stack (``models``/``explain``); ``tests/architecture`` enforces it.
"""

from provenance.graph.adjudicate import (
    Adjudication,
    CandidateEvent,
    ConfidenceBand,
    EvidenceBundle,
    Verdict,
    validate_event,
)
from provenance.graph.build import build_snapshot, station_points_from_metadata
from provenance.graph.snapshot import EdgeType, GraphSnapshot, NodeType
from provenance.graph.wind import WindField, WindProvenance, WindVector

__all__ = [
    "Adjudication",
    "CandidateEvent",
    "ConfidenceBand",
    "EdgeType",
    "EvidenceBundle",
    "GraphSnapshot",
    "NodeType",
    "Verdict",
    "WindField",
    "WindProvenance",
    "WindVector",
    "build_snapshot",
    "station_points_from_metadata",
    "validate_event",
]
