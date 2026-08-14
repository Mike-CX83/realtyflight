"""Geographic helpers: great-circle distance (Wave 2) + the local meters
frame and boundary polygon (Wave 3).

Keep ALL coordinate math in this one file: frame/unit bugs are the classic
drone failure mode (doc 01 S12), so they get one home and brutal tests.

Frame convention: LocalFrame is an East-North-Up tangent plane centered on a
chosen origin (we use the mission's home point). x = meters East, y = meters
North. Shapely is planar, so every containment/area check happens in this
frame — never on raw lat/lon.
"""

from __future__ import annotations

import math

import pymap3d
from shapely.geometry import Point, Polygon

from core.schema import GeoPoint

EARTH_RADIUS_M = 6_371_008.8  # IUGG mean Earth radius


def distance_m(a: GeoPoint, b: GeoPoint) -> float:
    """Great-circle (haversine) distance in meters.

    Accurate to well under 0.5% at property scale (tens to hundreds of
    meters), which is far tighter than our safety margins.
    """
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


class LocalFrame:
    """East-North meters plane centered on `origin` (the mission home).

    to_xy() is the ONLY sanctioned lat/lon -> meters conversion in the
    codebase. Altitudes are handled separately (relative AGL in the schema),
    so the Up component is ignored here.
    """

    def __init__(self, origin: GeoPoint) -> None:
        self.origin = origin

    def to_xy(self, p: GeoPoint) -> tuple[float, float]:
        e, n, _u = pymap3d.geodetic2enu(p.lat, p.lon, 0.0, self.origin.lat, self.origin.lon, 0.0)
        return (float(e), float(n))

    def point(self, p: GeoPoint) -> Point:
        return Point(self.to_xy(p))

    def polygon(self, vertices: list[GeoPoint]) -> Polygon:
        """Boundary polygon in local meters. Shapely auto-closes the ring.
        May be invalid (e.g. self-intersecting bow-tie) — callers must check
        .is_valid; GEO-01 turns that into a typed violation."""
        return Polygon([self.to_xy(v) for v in vertices])
