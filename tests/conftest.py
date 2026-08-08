"""Shared test fixtures.

Two rules this file enforces:

1. Determinism. Every test runs under a fixed seed, so a failure is reproducible
   from the test name alone.
2. No real data. Nothing here reads from data/raw. The test suite must pass on a
   fresh clone with an empty data directory, and CI checks that.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from pathlib import Path

import pandas as pd
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
def synthetic_corpus() -> tuple[pd.DataFrame, object]:
    """The seeded synthetic corpus and its ground-truth ledger."""
    from provenance.fixtures.generator import generate

    return generate()


@pytest.fixture
def clean_corpus() -> pd.DataFrame:
    """A corpus with no injected defects - should trip no detector."""
    from provenance.fixtures.generator import generate

    frame, _ = generate(inject=False)
    return frame


@pytest.fixture
def make_ctx() -> Callable[[pd.DataFrame], object]:
    """Factory: build an AuditContext (real thresholds + coverage) for a frame."""
    from provenance.config.loading import load_thresholds
    from provenance.detectors.base import AuditContext
    from provenance.grid.coverage import build_coverage

    def _factory(frame: pd.DataFrame) -> AuditContext:
        return AuditContext(thresholds=load_thresholds(), coverage=build_coverage(frame))

    return _factory


@pytest.fixture
def make_frame() -> Callable[..., pd.DataFrame]:
    """Factory: build a small canonical long frame from simple per-series specs."""
    from provenance.schema import canonical as C

    def _factory(rows: list[dict]) -> pd.DataFrame:
        frame = pd.DataFrame(rows)
        if C.INSTRUMENT_ID not in frame.columns:
            frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
        if C.SOURCE_FILE not in frame.columns:
            frame[C.SOURCE_FILE] = "test_air.csv"
        frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
        frame = C.add_row_hash(frame)
        return C.validate(frame)

    return _factory
