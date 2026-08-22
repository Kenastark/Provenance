"""Network-wide findings: a (reason_code, parameter) that fires on every carrying
station, not just one - see `orchestrator._network_wide_findings`.

Generic over both dimensions on purpose (standing rule 1/2): these tests trigger
a real detector (R07, physical maximum) rather than hand-injecting a reason code,
so the whole pipeline - detection, coverage, the fraction/station-coverage gate -
is exercised the same way a real audit run would.
"""

from __future__ import annotations

import pytest
from tests.support import series_rows

from provenance.audit.orchestrator import run_audit

pytestmark = pytest.mark.unit

_MAX_PM10 = 2000.0  # config/thresholds.yaml's physical_bounds.PM10.max


def test_finding_when_every_carrying_station_is_fully_affected(make_frame) -> None:
    # Both stations' every PM10 reading exceeds the max - a systemic fact, not a
    # station-specific fault.
    rows = series_rows("NET-A", "PM10", [3000.0] * 5) + series_rows("NET-B", "PM10", [3000.0] * 5)
    result = run_audit(make_frame(rows))

    matches = [
        f for f in result.network_wide_findings if f.reason_code == "R07" and f.parameter == "PM10"
    ]
    assert len(matches) == 1
    finding = matches[0]
    assert finding.station_count == 2
    assert finding.flagged_readings == 10
    assert finding.total_readings == 10
    assert finding.fraction == 1.0


def test_no_finding_when_only_one_carrying_station_is_affected(make_frame) -> None:
    # NET-A is entirely over the max; NET-B's readings are all ordinary. Even
    # though NET-A alone is 100% affected, this is a local fault, not systemic -
    # must not be reported as network-wide.
    rows = series_rows("NET-A", "PM10", [3000.0] * 5) + series_rows("NET-B", "PM10", [30.0] * 5)
    result = run_audit(make_frame(rows))

    assert not any(
        f.reason_code == "R07" and f.parameter == "PM10" for f in result.network_wide_findings
    )


def test_no_finding_when_the_fraction_is_below_the_configured_gate(make_frame) -> None:
    # Both stations are touched, but only 2 of 5 readings each (0.4 overall) trip
    # R07 - below thresholds.yaml's network_wide_finding.min_fraction (0.95), so
    # this is common, not systemic.
    values = [3000.0, 3000.0, 30.0, 30.0, 30.0]
    rows = series_rows("NET-A", "PM10", values) + series_rows("NET-B", "PM10", values)
    result = run_audit(make_frame(rows))

    assert not any(
        f.reason_code == "R07" and f.parameter == "PM10" for f in result.network_wide_findings
    )


def test_absence_pattern_codes_are_never_reported_as_network_wide(make_frame) -> None:
    """R01 (absent cell) has no *present* reading to compare against at all - a
    real bug this guards: an earlier version divided R01's absent-cell count by a
    raw present-reading count, which could put the numerator above the
    denominator (a nonsensical fraction over 1) whenever a parameter's real
    completeness was low - exactly what the real Green Sentinel drop's NO/NOx
    channels do. Both stations here carry the same 3-hour gap (hours 2-4), so R01
    fires on every carrying station - but it must still never appear, because an
    absence is a completeness story, not a "these readings are wrong" one.
    """
    # Values vary (30-33) so R12 zero-variance genuinely does not fire here too -
    # this test is isolating R01 specifically, not "any code that happens to fire".
    rows = (
        series_rows("NET-A", "PM10", [30.0, 31.0], start="2026-05-01T00:00:00")
        + series_rows("NET-A", "PM10", [32.0, 33.0], start="2026-05-01T05:00:00")
        + series_rows("NET-B", "PM10", [30.0, 31.0], start="2026-05-01T00:00:00")
        + series_rows("NET-B", "PM10", [32.0, 33.0], start="2026-05-01T05:00:00")
    )
    result = run_audit(make_frame(rows))

    assert not any(f.parameter == "PM10" for f in result.network_wide_findings)


def test_network_wide_findings_survive_the_summary_round_trip(make_frame) -> None:
    """`to_dict()` must carry the new field - the API serves `summary` verbatim."""
    rows = series_rows("NET-A", "PM10", [3000.0] * 3) + series_rows("NET-B", "PM10", [3000.0] * 3)
    result = run_audit(make_frame(rows))
    d = result.to_dict()
    assert "network_wide_findings" in d
    assert d["network_wide_findings"][0]["reason_code"] == "R07"
