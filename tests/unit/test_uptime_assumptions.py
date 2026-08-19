"""The assumptions the dashboard's derived uptime column rests on.

The Data Quality Monitor computes uptime as ``1 - (R01 absent cells / expected
cells)``, where expected cells is ``window_hours x n_parameters``. The API serves no
uptime field, so that arithmetic lives in the presentation layer - which is exactly
the kind of thing that drifts away from the engine's own definition without anyone
noticing.

These tests are the tether. They assert, on the backend, the two properties the
frontend's formula silently assumes. If either stops holding, a test here fails and
names the frontend file that has to change, rather than the dashboard quietly
reporting a wrong percentage.

The alternative - serving a computed uptime from the audit engine - is the right
long-term answer and is recorded as such; it is not done here because it would mean
adding a windowed aggregate to the audit run, which is engine work rather than
dashboard work.
"""

from __future__ import annotations

import pandas as pd
import pytest

from provenance.config.loading import load_schema_assumptions, load_thresholds
from provenance.detectors import registry
from provenance.detectors.base import REASON_CODE, AuditContext
from provenance.fixtures.generator import generate
from provenance.grid.coverage import build_coverage
from provenance.schema import canonical as C

HOURLY = pd.Timedelta(hours=1)


@pytest.fixture(scope="module")
def corpus() -> tuple[pd.DataFrame, object]:
    frame, _ = generate(n_stations=18)
    return frame, build_coverage(frame)


def test_every_station_series_is_hourly(corpus: tuple[pd.DataFrame, object]) -> None:
    """The uptime denominator is `window_hours x n_parameters`, i.e. one cell an hour.

    If a source with another cadence (the Enclod counters are 15-minute) ever becomes
    a station, that denominator is wrong and the column silently overstates uptime.

    Fix location: apps/web/src/features/quality/QualityMonitor.tsx, `buildRows`.
    """
    _, coverage = corpus
    offenders = {
        f"{key[0]}/{key[1]}": str(grid.cadence)
        for key, grid in coverage.series_grids.items()  # type: ignore[attr-defined]
        if grid.cadence != HOURLY
    }
    assert not offenders, (
        "The dashboard's uptime denominator assumes one cell per hour per parameter, "
        f"but these series are not hourly: {offenders}. Either serve uptime from the "
        "audit engine or make the frontend cadence-aware."
    )


def test_green_sentinel_cadence_is_still_declared_hourly() -> None:
    """The schema assumption the test above depends on, read from its own file."""
    assumptions = load_schema_assumptions()
    assert assumptions["green_sentinel"]["cadence"] == "hourly"


def test_r01_is_one_flag_per_absent_cell(corpus: tuple[pd.DataFrame, object]) -> None:
    """Uptime counts R01 rows, so R01 must be per-cell, not per-run.

    R02 promotes a long run of absences to a communication gap; if R01 were ever
    collapsed into runs the same way, the numerator would count outages instead of
    hours and uptime would read far too high.
    """
    frame, coverage = corpus
    defects = registry.run_detectors(
        frame, AuditContext(thresholds=load_thresholds(), coverage=coverage)
    )
    r01 = defects[defects[REASON_CODE] == "R01"]

    assert not r01.empty, "the fixture corpus injects absences; R01 should fire"
    # One row per (station, parameter, timestamp): no duplicates, no collapsing.
    cells = r01[[C.STATION_ID, C.PARAMETER, C.TIMESTAMP]]
    assert len(cells) == len(cells.drop_duplicates()), "R01 emitted a duplicate cell"

    # And the count matches the coverage model's own absent-cell tally.
    assert len(r01) == coverage.n_absent_cells()  # type: ignore[attr-defined]
