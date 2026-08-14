"""The distance function gets brutal tests — coordinate math is where drone
software traditionally goes wrong (doc 01 S12)."""

from __future__ import annotations

import math

import pytest

from core.geo import distance_m
from core.schema import GeoPoint


def P(lat: float, lon: float) -> GeoPoint:
    return GeoPoint(lat=lat, lon=lon)


def test_zero_distance():
    a = P(36.154, -95.9928)
    assert distance_m(a, a) == 0.0


def test_symmetry():
    a, b = P(36.154, -95.9928), P(36.155, -95.9910)
    assert distance_m(a, b) == pytest.approx(distance_m(b, a), rel=1e-12)


def test_one_millidegree_latitude_is_about_111m():
    # 0.001 deg of latitude ~ 111.2 m anywhere on Earth
    a, b = P(36.1540, -95.9928), P(36.1550, -95.9928)
    assert distance_m(a, b) == pytest.approx(111.2, abs=1.0)


def test_longitude_shrinks_with_latitude():
    # 0.001 deg of longitude at 36N ~ 111.32 * cos(36) ~ 90.0 m
    a, b = P(36.1540, -95.9928), P(36.1540, -95.9918)
    expected = 111_195.0 * 0.001 * math.cos(math.radians(36.154))
    assert distance_m(a, b) == pytest.approx(expected, rel=0.01)


def test_known_city_pair_sanity():
    # Tulsa (36.1540,-95.9928) to Oklahoma City (35.4676,-97.5164) ~ 157 km
    d = distance_m(P(36.1540, -95.9928), P(35.4676, -97.5164))
    assert d == pytest.approx(157_000, rel=0.02)


def test_equator_vs_pole_hemispheres():
    # crossing the equator and the antimeridian must not blow up
    assert distance_m(P(-0.001, 179.999), P(0.001, -179.999)) < 500.0
