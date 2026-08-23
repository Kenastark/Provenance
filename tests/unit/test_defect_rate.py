"""The single defect-rate definition."""

from __future__ import annotations

import pytest

from provenance.grid.defect_rate import DEFINITION, DefectRate


def test_rate_is_ratio() -> None:
    assert DefectRate(25, 100).rate == 0.25
    assert DefectRate(25, 100).percent == 25.0


def test_zero_covered_is_zero_rate() -> None:
    assert DefectRate(0, 0).rate == 0.0


def test_numerator_cannot_exceed_denominator() -> None:
    with pytest.raises(ValueError, match="subset"):
        DefectRate(101, 100)


def test_negative_counts_rejected() -> None:
    with pytest.raises(ValueError):
        DefectRate(-1, 100)


def test_definition_travels_with_the_number() -> None:
    dr = DefectRate(1, 10)
    assert dr.definition == DEFINITION
    assert "structural" in dr.definition.lower()


def test_definition_does_not_claim_every_cell_is_an_hour() -> None:
    """The grid reindexes each series at its own inferred cadence - air and groundwater
    hourly, noise daily (``grid.coverage``). The definition string renders verbatim into
    audit.md, audit.html and the regulatory export, so wording it as "(station, parameter,
    hour)" misdescribes every daily cell to the person most likely to check. Pinned here
    because the arithmetic and the sentence describing it must not drift apart."""
    lowered = DEFINITION.lower()
    assert "hour)" not in lowered
    assert "tick" in lowered
    assert "cadence" in lowered
