"""Shared test fixtures.

Two rules this file enforces:

1. Determinism. Every test runs under a fixed seed, so a failure is reproducible
   from the test name alone.
2. No real data. Nothing here reads from data/raw. The test suite must pass on a
   fresh clone with an empty data directory, and CI checks that.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from pathlib import Path

import pytest

SEED = 20260907


@pytest.fixture(autouse=True)
def _deterministic() -> Iterator[None]:
    """Reset RNG state before every test."""
    random.seed(SEED)
    try:
        import numpy as np

        np.random.seed(SEED)
    except ImportError:  # pragma: no cover - numpy is a hard dependency in practice
        pass
    yield


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """An isolated directory for tests that write files."""
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.fixture
def synthetic_corpus() -> None:
    """Seeded synthetic corpus with a ground-truth defect ledger.

    Filled in by phase 1 (`provenance.fixtures`). Every detector, property, and
    golden test builds on this rather than on the real export.
    """
    pytest.skip("synthetic corpus generator lands in phase 1")
