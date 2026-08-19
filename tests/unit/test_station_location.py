"""Parsing the Green Sentinel ``Location`` column into a site name and coordinates.

The format strings below are the real ones, read from the export at flag-review
time (e.g. DEB-KER01 = 'ÉNYGÖ, BMW körút (47.577175, 21.502204)'). The parser is
verified against them, not against a guessed format, and fails loudly otherwise.
"""

from __future__ import annotations

import pytest

from provenance.io.loaders import parse_location
from provenance.schema.canonical import SchemaDriftError


def test_parses_the_verified_real_format() -> None:
    name, lat, lon = parse_location("ÉNYGÖ, BMW körút (47.577175, 21.502204)")
    assert name == "ÉNYGÖ, BMW körút"  # site name may itself contain a comma
    assert lat == pytest.approx(47.577175)
    assert lon == pytest.approx(21.502204)
    # Debrecen sits ~47.5 N, ~21.6 E: latitude first, longitude second.
    assert 47.0 < lat < 48.0
    assert 21.0 < lon < 22.0


def test_parses_a_name_without_a_comma() -> None:
    name, lat, lon = parse_location("Petőfi tér (47.52324542, 21.6337404)")
    assert name == "Petőfi tér"
    assert (lat, lon) == (pytest.approx(47.52324542), pytest.approx(21.6337404))


def test_fails_loudly_when_the_coordinate_pair_is_absent() -> None:
    with pytest.raises(SchemaDriftError, match="Location"):
        parse_location("Some site with no coordinates")


def test_fails_loudly_on_a_non_numeric_coordinate() -> None:
    with pytest.raises(SchemaDriftError):
        parse_location("Bad (north, east)")
