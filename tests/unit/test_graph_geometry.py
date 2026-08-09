"""Geodesic primitives, and the wraparound bug this module exists to not have."""

from __future__ import annotations

import math

import pytest

from provenance.graph import geometry as geo


def test_haversine_zero_distance() -> None:
    assert geo.haversine_km(47.53, 21.55, 47.53, 21.55) == pytest.approx(0.0, abs=1e-9)


def test_haversine_known_scale() -> None:
    # ~3 km due east at Debrecen's latitude (0.04° lon).
    d = geo.haversine_km(47.53, 21.55, 47.53, 21.59)
    assert 2.9 < d < 3.1


def test_haversine_symmetric() -> None:
    a = geo.haversine_km(47.5, 21.5, 47.6, 21.7)
    b = geo.haversine_km(47.6, 21.7, 47.5, 21.5)
    assert a == pytest.approx(b)


def test_bearing_cardinals() -> None:
    assert geo.initial_bearing_deg(47.53, 21.55, 47.63, 21.55) == pytest.approx(0.0, abs=0.1)  # N
    assert geo.initial_bearing_deg(47.53, 21.55, 47.53, 21.59) == pytest.approx(90.0, abs=0.1)  # E
    assert geo.initial_bearing_deg(47.53, 21.55, 47.43, 21.55) == pytest.approx(180.0, abs=0.1)  # S
    assert geo.initial_bearing_deg(47.53, 21.55, 47.53, 21.51) == pytest.approx(270.0, abs=0.1)  # W


def test_bearing_in_range() -> None:
    b = geo.initial_bearing_deg(47.53, 21.55, 47.40, 21.40)
    assert 0.0 <= b < 360.0


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (359.0, 1.0, 2.0),  # the classic seam bug: NOT 358
        (1.0, 359.0, 2.0),
        (10.0, 350.0, 20.0),
        (0.0, 180.0, 180.0),
        (90.0, 90.0, 0.0),
        (270.0, 90.0, 180.0),
        (45.0, 135.0, 90.0),
    ],
)
def test_angular_difference_wraps(a: float, b: float, expected: float) -> None:
    assert geo.angular_difference_deg(a, b) == pytest.approx(expected)
    # Symmetric.
    assert geo.angular_difference_deg(b, a) == pytest.approx(expected)


def test_angular_difference_bounded() -> None:
    for a in range(0, 360, 7):
        for b in range(0, 360, 11):
            d = geo.angular_difference_deg(float(a), float(b))
            assert 0.0 <= d <= 180.0


def test_wind_travel_is_opposite_of_source() -> None:
    # Wind FROM the west (270°) travels toward the east (90°).
    assert geo.wind_travel_bearing_deg(270.0) == pytest.approx(90.0)
    assert geo.wind_travel_bearing_deg(0.0) == pytest.approx(180.0)
    assert geo.wind_travel_bearing_deg(350.0) == pytest.approx(170.0)


def test_wrap_360() -> None:
    assert geo.wrap_360(370.0) == pytest.approx(10.0)
    assert geo.wrap_360(-10.0) == pytest.approx(350.0)


def test_bearing_reverse_relationship_planar_limit() -> None:
    # Over a short east-west hop the reverse bearing is ~180° from the forward one.
    fwd = geo.initial_bearing_deg(47.53, 21.55, 47.53, 21.59)
    rev = geo.initial_bearing_deg(47.53, 21.59, 47.53, 21.55)
    assert geo.angular_difference_deg(fwd, rev) == pytest.approx(180.0, abs=0.2)


def test_haversine_matches_manual_equatorial() -> None:
    # One degree of latitude is ~111.19 km on this sphere.
    d = geo.haversine_km(0.0, 0.0, 1.0, 0.0)
    assert d == pytest.approx(math.pi * geo.EARTH_RADIUS_KM / 180.0, rel=1e-6)
