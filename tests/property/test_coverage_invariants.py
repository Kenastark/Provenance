"""Coverage identities that must hold for ANY generated corpus.

These are the guardrails on the most error-prone part of the audit: the split
between observed, absent, and structurally-excluded cells. If any of them breaks,
the defect rate is wrong, so they are property-tested rather than spot-checked.
"""

from __future__ import annotations

import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from provenance.fixtures.generator import generate
from provenance.grid.coverage import build_coverage
from provenance.schema import canonical as C

_DAYS = st.integers(min_value=3, max_value=12)


@settings(max_examples=15, deadline=None)
@given(n_days=_DAYS)
def test_expected_equals_observed_plus_absent_plus_structural(n_days: int) -> None:
    frame, _ = generate(n_days=n_days, inject=False)
    m = build_coverage(frame)
    assert m.n_expected_cells() == (
        m.n_observed_cells() + m.n_absent_cells() + m.n_structurally_excluded_cells()
    )


def test_identity_holds_on_the_injected_corpus() -> None:
    # The same identity, on a corpus carrying every injected defect (n_days=14).
    frame, _ = generate()
    m = build_coverage(frame)
    assert m.n_expected_cells() == (
        m.n_observed_cells() + m.n_absent_cells() + m.n_structurally_excluded_cells()
    )
    assert m.n_structurally_excluded_cells() > 0


@settings(max_examples=15, deadline=None)
@given(n_days=_DAYS)
def test_observed_is_subset_of_expected(n_days: int) -> None:
    frame, _ = generate(n_days=n_days, inject=False)
    m = build_coverage(frame)
    # Reindexing never invents a reading: every observed cell sits in the grid.
    for (station, parameter), g in frame.groupby([C.STATION_ID, C.PARAMETER]):
        grid = m.series_grids[(str(station), str(parameter))]
        observed = pd.DatetimeIndex(g[C.TIMESTAMP].unique())
        full = pd.date_range(grid.start, grid.end, freq=grid.cadence)
        assert observed.isin(full).all()
        assert grid.n_observed + grid.n_absent == grid.n_expected


@settings(max_examples=10, deadline=None)
@given(n_days=_DAYS)
def test_observed_cell_count_matches_unique_readings(n_days: int) -> None:
    frame, _ = generate(n_days=n_days, inject=False)
    m = build_coverage(frame)
    unique = frame[[C.STATION_ID, C.PARAMETER, C.TIMESTAMP]].drop_duplicates()
    assert m.n_observed_cells() == len(unique)
