"""Wave-3 rule tests: boundary geometry. Edge cases get special attention —
points ON the line, orbits that barely clip, bow-tie polygons."""

from __future__ import annotations

import pytest

from core.geo import LocalFrame
from core.policy.engine import parse_and_validate, validate_plan
from core.schema import GeoPoint, MissionPlan


def _plan(d) -> MissionPlan:
    return MissionPlan.model_validate(d)


# ---------------------------------------------------------------------------- #
# LocalFrame sanity (the sanctioned lat/lon -> meters conversion)
# ---------------------------------------------------------------------------- #


def test_localframe_origin_is_zero():
    o = GeoPoint(lat=36.1536, lon=-95.9932)
    x, y = LocalFrame(o).to_xy(o)
    assert abs(x) < 1e-6 and abs(y) < 1e-6


def test_localframe_north_is_positive_y():
    o = GeoPoint(lat=36.1536, lon=-95.9932)
    x, y = LocalFrame(o).to_xy(GeoPoint(lat=36.1546, lon=-95.9932))  # +0.001 deg lat
    assert abs(x) < 0.5
    assert y == pytest.approx(111.0, abs=1.5)


def test_localframe_east_is_positive_x():
    o = GeoPoint(lat=36.1536, lon=-95.9932)
    x, y = LocalFrame(o).to_xy(GeoPoint(lat=36.1536, lon=-95.9922))  # +0.001 deg lon
    assert abs(y) < 0.5
    assert x == pytest.approx(89.8, abs=1.5)  # 111.32 km/deg * cos(36.15)


def test_localframe_agrees_with_haversine():
    from core.geo import distance_m
    import math

    o = GeoPoint(lat=36.1536, lon=-95.9932)
    p = GeoPoint(lat=36.1544, lon=-95.9921)
    x, y = LocalFrame(o).to_xy(p)
    assert math.hypot(x, y) == pytest.approx(distance_m(o, p), rel=0.001)


# ---------------------------------------------------------------------------- #
# GEO-01 — boundary sanity
# ---------------------------------------------------------------------------- #


def test_geo01_good_boundary_passes(good_plan: MissionPlan):
    report = validate_plan(good_plan)
    assert [r for r in report.results if r.rule == "GEO-01"][0].passed


def test_geo01_bowtie_self_intersection(good_dict):
    # swap two vertices so edges cross (bow-tie)
    b = good_dict["property"]["boundary"]
    b[1], b[2] = b[2], b[1]
    report = validate_plan(_plan(good_dict))
    v = [x for x in report.violations if x.rule == "GEO-01"][0]
    assert "invalid" in v.message.lower() or "self-intersection" in v.message.lower()


def test_geo01_area_too_small(good_dict):
    c = good_dict["property"]["home"]
    d = 0.00003  # ~3 m half-side => ~44 m2 (< 100 m2 minimum)
    good_dict["property"]["boundary"] = [
        {"lat": c["lat"] + d, "lon": c["lon"] - d},
        {"lat": c["lat"] + d, "lon": c["lon"] + d},
        {"lat": c["lat"] - d, "lon": c["lon"] + d},
        {"lat": c["lat"] - d, "lon": c["lon"] - d},
    ]
    report = validate_plan(_plan(good_dict))
    assert any(v.rule == "GEO-01" and "below" in v.message for v in report.violations)


def test_geo01_area_too_large(good_dict):
    c = good_dict["property"]["center"]
    d = 0.005  # ~550 m half-side => ~1.2 km2 (> 0.25 km2 max)
    good_dict["property"]["boundary"] = [
        {"lat": c["lat"] + d, "lon": c["lon"] - d},
        {"lat": c["lat"] + d, "lon": c["lon"] + d},
        {"lat": c["lat"] - d, "lon": c["lon"] + d},
        {"lat": c["lat"] - d, "lon": c["lon"] - d},
    ]
    report = validate_plan(_plan(good_dict))
    assert any(v.rule == "GEO-01" and "exceeds" in v.message for v in report.violations)


# ---------------------------------------------------------------------------- #
# GEO-02 — home placement
# ---------------------------------------------------------------------------- #


def test_geo02_good_home_passes(good_plan: MissionPlan):
    report = validate_plan(good_plan)
    assert [r for r in report.results if r.rule == "GEO-02"][0].passed


def test_geo02_home_outside_boundary(good_dict):
    good_dict["property"]["home"] = {"lat": 36.1560, "lon": -95.9950}  # well outside
    report = validate_plan(_plan(good_dict))
    v = [x for x in report.violations if x.rule == "GEO-02"][0]
    assert "outside" in v.message


def test_geo02_home_on_the_fence_line(good_dict):
    # exactly on the west edge: inside by containment rules or not, the 2 m
    # margin must reject it either way
    good_dict["property"]["home"] = {"lat": 36.15400, "lon": -95.99330}
    report = validate_plan(_plan(good_dict))
    assert "GEO-02" in report.failed_rules()


def test_geo02_home_one_meter_from_fence(good_dict):
    # ~1 m east of the west edge: inside, but under the 2 m margin
    good_dict["property"]["home"] = {"lat": 36.15400, "lon": -95.99328878}
    report = validate_plan(_plan(good_dict))
    v = [x for x in report.violations if x.rule == "GEO-02"][0]
    assert "margin" in v.message


# ---------------------------------------------------------------------------- #
# GEO-03 — flight containment
# ---------------------------------------------------------------------------- #


def test_geo03_good_flight_passes(good_plan: MissionPlan):
    report = validate_plan(good_plan)
    assert [r for r in report.results if r.rule == "GEO-03"][0].passed


def test_geo03_waypoint_outside(good_dict):
    good_dict["steps"][1]["to"] = {"lat": 36.15500, "lon": -95.99280}  # north of fence
    report = validate_plan(_plan(good_dict))
    assert any(v.rule == "GEO-03" and v.step == 1 for v in report.violations)


def test_geo03_waypoint_inside_but_within_margin(good_dict):
    # ~1.5 m from the north edge: inside the fence, inside nothing after the 3 m shrink
    good_dict["steps"][1]["to"] = {"lat": 36.154487, "lon": -95.99280}
    report = validate_plan(_plan(good_dict))
    assert any(v.rule == "GEO-03" and v.step == 1 for v in report.violations)


def test_geo03_orbit_ring_clips_fence(good_dict):
    good_dict["steps"][3]["radius_m"] = 45.0  # square is ~90x111 m; 45+2.5 ring clips E/W
    report = validate_plan(_plan(good_dict))
    v = [x for x in report.violations if x.rule == "GEO-03" and x.step == 3][0]
    assert "orbit ring" in v.message


def test_geo03_orbit_fits_when_shrunk(good_dict):
    good_dict["steps"][3]["radius_m"] = 30.0  # ring at 32.5 m: fits the ~90 m-wide square w/ margin
    report = validate_plan(_plan(good_dict))
    geo03 = [r for r in report.results if r.rule == "GEO-03"][0]
    assert geo03.passed, [v.message for v in report.violations]


def test_geo03_invalid_boundary_fails_closed(good_dict):
    b = good_dict["property"]["boundary"]
    b[1], b[2] = b[2], b[1]  # bow-tie
    report = validate_plan(_plan(good_dict))
    # deny-by-default: GEO-02 and GEO-03 must fail too, not silently skip
    assert {"GEO-01", "GEO-02", "GEO-03"} <= set(report.failed_rules())


# ---------------------------------------------------------------------------- #
# Evil plans, Wave-3 edition
# ---------------------------------------------------------------------------- #

EVIL_CASES = [
    (
        "orbit_the_whole_block",  # radius 80 on a ~90 m-wide lot
        lambda d: d["steps"][3].update(radius_m=80.0),
        {"GEO-03"},
    ),
    (
        "launch_from_the_street",  # home outside the drawn property
        lambda d: d["property"].update(home={"lat": 36.15340, "lon": -95.99340}),
        {"GEO-02"},
    ),
    (
        "bowtie_boundary",
        lambda d: d["property"]["boundary"].__setitem__(
            slice(1, 3), [d["property"]["boundary"][2], d["property"]["boundary"][1]]
        ),
        {"GEO-01", "GEO-02", "GEO-03"},
    ),
]


@pytest.mark.parametrize(("name", "mutator", "expected"), EVIL_CASES, ids=[c[0] for c in EVIL_CASES])
def test_wave3_evil_plans_die_with_the_right_rules(good_dict, name, mutator, expected):
    mutator(good_dict)
    plan, report = parse_and_validate(good_dict)
    assert not report.ok, f"evil plan '{name}' was approved!"
    fired = set(report.failed_rules())
    assert expected <= fired, f"'{name}' should trip at least {expected}, got {fired}"
