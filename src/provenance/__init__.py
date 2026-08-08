"""Provenance - an AI trust layer for environmental sensor networks.

The package is organised as a pipeline. Read it in this order:

    io -> schema -> grid -> detectors -> audit -> trust -> graph -> models -> explain

`api` and `report` are presentation layers and must never be imported by anything
upstream of them. `tests/architecture` enforces that.
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
