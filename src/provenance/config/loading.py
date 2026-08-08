"""Typed access to the YAML config that sits beside this module.

The config layer is the root of the dependency graph (see
``tests/architecture/test_layering.py``): it imports nothing downstream. These
loaders read the two hand-maintained YAML files and are cached so every caller
sees the same object.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent
THRESHOLDS_PATH = _CONFIG_DIR / "thresholds.yaml"
SCHEMA_ASSUMPTIONS_PATH = _CONFIG_DIR / "schema_assumptions.yaml"
STATION_ZONES_PATH = _CONFIG_DIR / "station_zones.yaml"


@lru_cache(maxsize=1)
def load_thresholds() -> dict[str, Any]:
    """Detector thresholds, keyed as in ``thresholds.yaml``."""
    data: dict[str, Any] = yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    return data


@lru_cache(maxsize=1)
def load_schema_assumptions() -> dict[str, Any]:
    """Everything the loaders assume about the input files."""
    data: dict[str, Any] = yaml.safe_load(SCHEMA_ASSUMPTIONS_PATH.read_text(encoding="utf-8"))
    return data


@lru_cache(maxsize=1)
def load_station_zones() -> dict[str, str]:
    """Curated station_id -> zone_type map (provisional; see station_zones.yaml).

    Human curation, not a measurement: the export carries no zone column. Returns a
    flat ``{station_id: zone}`` map; stations absent from the file (e.g. the synthetic
    fixtures) get no zone, and the caller leaves ``zone_type`` null rather than
    inventing one.
    """
    data: dict[str, Any] = yaml.safe_load(STATION_ZONES_PATH.read_text(encoding="utf-8"))
    stations = data.get("stations", {}) or {}
    return {str(sid): str(spec["zone"]) for sid, spec in stations.items()}


def config_hash() -> str:
    """A stable short digest of both config files, for run provenance.

    Two audits with byte-identical config produce the same hash; a threshold
    edit changes it, so a report can be tied to the exact settings that made it.
    """
    import hashlib

    h = hashlib.sha256()
    for path in (SCHEMA_ASSUMPTIONS_PATH, THRESHOLDS_PATH):
        h.update(path.read_bytes())
    return h.hexdigest()[:16]
