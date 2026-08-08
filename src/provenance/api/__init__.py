"""The public API surface. Presentation layer only — never imported upstream."""

from __future__ import annotations

from provenance.api.app import create_app

__all__ = ["create_app"]
