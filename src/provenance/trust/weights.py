"""Typed access to ``trust_weights.yaml``.

Cached like the other config loaders. The weights are elicited, not fitted, and
the file says so; nothing here hides that provenance.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent / "config"
TRUST_WEIGHTS_PATH = _CONFIG_DIR / "trust_weights.yaml"


@lru_cache(maxsize=1)
def load_trust_weights() -> dict[str, Any]:
    """The trust-score weights and component parameters."""
    data: dict[str, Any] = yaml.safe_load(TRUST_WEIGHTS_PATH.read_text(encoding="utf-8"))
    return data


def trust_config_hash() -> str:
    """Short digest of the trust weights file, for run provenance."""
    return hashlib.sha256(TRUST_WEIGHTS_PATH.read_bytes()).hexdigest()[:16]
