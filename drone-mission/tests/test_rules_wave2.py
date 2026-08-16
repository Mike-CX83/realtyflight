"""Wave-2 rule tests: numeric envelopes. Pattern per doc 11 §5 —
each rule: >=1 pass case, >=2 fail cases, exact rule IDs asserted."""

from __future__ import annotations

import pytest

from core.policy.engine import parse_and_validate, validate_plan
from core.schema import MissionPlan


def _plan(d) -> MissionPlan:
    return MissionPlan.model_validate(d)


def test_good_plan_passes_all_wave2_rules(good_plan: MissionPlan):
    report = validate_plan(good_plan)
    assert report.ok, f"unexpected violations: {report.violations}"
    assert {"GEO-04", "KIN-01", "KIN-02", "GEO-05"} <= {r.rule for r in report.results}


# ---------------------------------------------------------------------------- #
# GEO-04 — altitude envelope
# ---------------------------------------------------------------------------- #


def test_geo04_orbit_above_mission_ceiling(good_dict):
    good_dict["steps"][3]["alt_m"] = 60.0  # schema-legal (<=120), mission ceiling is 40
    report = validate_plan(_plan(good_dict))
    v = [x for x in report.violations if x.rule == "GEO-04"][0]
    assert v.step == 3 and v.value == 60.0 and v.limit == 40.0


def test_geo04_goto_above_custom_ceiling(good_dict):
    good_dict["limits"] = {"max_alt_m": 30.0}
    report = validate_plan(_plan(good_dict))  # fixture flies at 25/38 m
    assert "GEO-04" in report.failed_rules()
    assert any(v.step == 4 for v in report.violations if v.rule == "GEO-04")  # the 38 m goto


def test_geo04_takeoff_below_floor(good_dict):
    good_dict["steps"][0]["alt_m"] = 3.0
    report = validate_plan(_plan(good_dict))
    assert any(v.rule == "GEO-04" and "floor" in v.message for v in report.violations)


def test_geo04_orbit_below_floor(good_dict):
    good_dict["steps"][3]["alt_m"] = 5.0
    report = validate_plan(_plan(good_dict))
    assert any(v.rule == "GEO-04" and v.step == 3 for v in report.violations)


def test_geo04_pass_at_exact_ceiling(good_dict):
    good_dict["steps"][4]["alt_m"] = 40.0  # exactly the default ceiling: allowed
    report = validate_plan(_plan(good_dict))
    geo04 = [r for r in report.results if r.rule == "GEO-04"][0]
    assert geo04.passed


# ---------------------------------------------------------------------------- #
# KIN-01 — speed cap
# ---------------------------------------------------------------------------- #


def test_kin01_goto_over_mission_cap(good_dict):
    good_dict["steps"][1]["speed_ms"] = 7.0  # schema-legal (<=8), mission cap 5
    report = validate_plan(_plan(good_dict))
    v = [x for x in report.violations if x.rule == "KIN-01"][0]
    assert v.step == 1 and v.value == 7.0 and v.limit == 5.0


def test_kin01_tightened_cap_catches_orbit(good_dict):
    good_dict["limits"] = {"max_speed_ms": 2.0}
    report = validate_plan(_plan(good_dict))  # orbit flies 3.0
    assert any(v.rule == "KIN-01" and v.step == 3 for v in report.violations)


def test_kin01_pass_at_exact_cap(good_dict):
    good_dict["steps"][1]["speed_ms"] = 5.0
    report = validate_plan(_plan(good_dict))
    kin01 = [r for r in report.results if r.rule == "KIN-01"][0]
    assert kin01.passed


# ---------------------------------------------------------------------------- #
# KIN-02 — orbit radius vs arrival tolerance
# ---------------------------------------------------------------------------- #


def test_kin02_radius_too_small_for_tolerance(good_dict):
    good_dict["limits"] = {"acceptance_radius_m": 10.0}  # 1.5x => min radius 15
    good_dict["steps"][3]["radius_m"] = 12.0
    report = validate_plan(_plan(good_dict))
    v = [x for x in report.violations if x.rule == "KIN-02"][0]
    assert v.step == 3 and v.limit == 15.0


def test_kin02_boundary_exact_min_passes(good_dict):
    good_dict["limits"] = {"acceptance_radius_m": 10.0}
    good_dict["steps"][3]["radius_m"] = 15.0
    report = validate_plan(_plan(good_dict))
    kin02 = [r for r in report.results if r.rule == "KIN-02"][0]
    assert kin02.passed


def test_kin02_default_tolerance_passes(good_plan: MissionPlan):
    report = validate_plan(good_plan)
    assert [r for r in report.results if r.rule == "KIN-02"][0].passed


# ---------------------------------------------------------------------------- #
# GEO-05 — distance from home
# ---------------------------------------------------------------------------- #


def test_geo05_faraway_goto(good_dict):
    good_dict["steps"][1]["to"] = {"lat": 36.1560, "lon": -95.9928}  # ~230 m out
    report = validate_plan(_plan(good_dict))
    v = [x for x in report.violations if x.rule == "GEO-05"][0]
    assert v.step == 1 and v.value > 150


def test_geo05_orbit_worst_point_counts_radius(good_dict):
    # center ~57 m out; radius 95 => worst point ~152 m > 150 cap
    good_dict["steps"][3]["radius_m"] = 95.0
    report = validate_plan(_plan(good_dict))
    assert any(v.rule == "GEO-05" and v.step == 3 for v in report.violations)


def test_geo05_tightened_cap(good_dict):
    good_dict["limits"] = {"max_home_dist_m": 50.0}
    report = validate_plan(_plan(good_dict))  # fixture's goto is ~69 m out
    assert "GEO-05" in report.failed_rules()


def test_geo05_default_plan_passes(good_plan: MissionPlan):
    report = validate_plan(good_plan)
    assert [r for r in report.results if r.rule == "GEO-05"][0].passed


# ---------------------------------------------------------------------------- #
# Evil plans, Wave-2 edition — through the full parse_and_validate pipeline
# ---------------------------------------------------------------------------- #

EVIL_CASES = [
    (
        "neighbors_yard",  # "fly over the neighbor's place" — far waypoint
        lambda d: d["steps"][1].update(to={"lat": 36.1585, "lon": -95.9928}),
        {"GEO-05"},
    ),
    (
        "too_high",  # 100 m is schema-legal but far above the 40 m mission ceiling
        lambda d: d["steps"][3].update(alt_m=100.0),
        {"GEO-04"},
    ),
    (
        "speed_demon",  # max the schema allows, still over the mission cap
        lambda d: d["steps"][1].update(speed_ms=8.0),
        {"KIN-01"},
    ),
    (
        "everything_wrong_at_once",
        lambda d: (
            d["steps"][1].update(speed_ms=8.0, alt_m=100.0),
            d["steps"].pop(),  # and skip landing
        ),
        {"KIN-01", "GEO-04", "SEQ-01"},
    ),
]


@pytest.mark.parametrize(
    ("name", "mutator", "expected"), EVIL_CASES, ids=[c[0] for c in EVIL_CASES]
)
def test_wave2_evil_plans_die_with_the_right_rules(good_dict, name, mutator, expected):
    mutator(good_dict)
    plan, report = parse_and_validate(good_dict)
    assert not report.ok, f"evil plan '{name}' was approved!"
    fired = set(report.failed_rules())
    assert expected <= fired, f"'{name}' should trip at least {expected}, got {fired}"
