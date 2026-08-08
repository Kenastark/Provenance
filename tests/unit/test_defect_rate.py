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
