"""The feature layer: meteorology and time, assembled honestly.

Everything the tree models learn from lives here. Two rules govern it, both from
CLAUDE.md:

* **Never invent a field or a unit** (standing rule 2). Weather features come from
  the network's own in-situ sensors where those exist (``Wind_Speed``,
  ``Wind_Direction``, ``Humidity``, ``Pressure`` are confirmed parameters in the
  export). Fields the export does not carry — air temperature, precipitation, the
  boundary-layer height — would come from the HungaroMet feed, whose schema is
  unconfirmed (``schema_assumptions.yaml``: ``weather``). Until it lands they are
  filled by a documented proxy and flagged, never silently zeroed.
* **Every feature carries its provenance** (§5.3). ``build_features`` returns the
  matrix *and* a :class:`FeatureSet` describing where each column came from, so the
  model card can be honest about which inputs are measured, which are proxies, and
  which are unavailable.

Wind direction is encoded as ``(sin, cos)`` rather than raw degrees, because 359°
and 1° are one degree apart on the compass but 358 units apart as a number, and a
tree that splits on the raw value learns a discontinuity that is not in the wind.
The test gate asserts exactly that difference.
"""

from __future__ import annotations

from provenance.models.features.build import build_features
from provenance.models.features.provenance import (
    FeatureProvenance,
    FeatureSet,
    FeatureSpec,
)
from provenance.models.features.wind import encode_wind_direction

__all__ = [
    "FeatureProvenance",
    "FeatureSet",
    "FeatureSpec",
    "build_features",
    "encode_wind_direction",
]
