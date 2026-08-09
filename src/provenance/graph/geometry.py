"""Geodesic geometry for the wind-conditioned graph.

Three primitives, and every one of them has a classic bug this module exists to
not have:

* :func:`haversine_km` — great-circle distance, not planar Pythagoras, because a
  degree of longitude at Debrecen's latitude (~47.5°N) is ~0.67 of a degree of
  latitude and a planar metric would distort east-west spacing by a third.
* :func:`initial_bearing_deg` — the forward azimuth of the i→j great circle at i,
  in [0, 360)° clockwise from north.
* :func:`angular_difference_deg` — the *wrapped* gap between two bearings, in
  [0, 180]°. Bearing 359° and wind 1° are 2° apart, not 358°. Getting this wrong
  is the single most common error in wind-direction code, so it is a named
  function with its own test rather than an inline ``abs(a - b)``.

Projection choice (documented deliberately, per the phase brief): distances and
bearings are computed on a **sphere** of radius :data:`EARTH_RADIUS_KM`, not on
the WGS84 ellipsoid. Over the network's ~15 km extent the spherical-vs-ellipsoidal
azimuth error is well under 0.1° and the distance error under ~0.3%, both far below
the precision a dispersion-cone weight needs; the sphere buys determinism and zero
dependencies. If sub-metre geodesy is ever required, swap this module for pyproj's
Geod without touching a caller.
"""

from __future__ import annotations

import math

# Mean Earth radius (km). The spherical model's one constant.
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two decimal-degree points, in kilometres."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Forward azimuth from point 1 to point 2, degrees clockwise from north in [0, 360).

    This is the compass bearing you would set off on to walk the great circle from
    (lat1, lon1) toward (lat2, lon2); it is *not* symmetric — the reverse bearing is
    not simply this ±180 except in the planar limit.
    """
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    theta = math.atan2(x, y)
    return (math.degrees(theta) + 360.0) % 360.0


def wrap_360(degrees: float) -> float:
    """Normalise an angle to [0, 360)."""
    return degrees % 360.0


def angular_difference_deg(a_deg: float, b_deg: float) -> float:
    """Smallest unsigned separation between two bearings, in [0, 180]°.

    Wraps correctly across the 0/360 seam: ``angular_difference_deg(359, 1) == 2``.
    """
    diff = (a_deg - b_deg + 180.0) % 360.0 - 180.0
    return abs(diff)


def wind_travel_bearing_deg(wind_from_deg: float) -> float:
    """The bearing the air is *travelling toward*, given the reported bearing it comes FROM.

    Meteorological convention reports the direction wind blows *from* (a northerly is
    0°, air moving south). A plume rides the air, so it travels toward
    ``(wind_from_deg + 180) mod 360``. Downwind alignment is measured against this.
    """
    return (wind_from_deg + 180.0) % 360.0
