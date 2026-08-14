"""Wave-1 rule tests — table-driven: every rule has pass cases and fail cases,
and every fail asserts the exact rule ID (doc 11 §5)."""

from __future__ import annotations

import pytest

from core.policy.engine import parse_and_validate, validate_plan
from core.schema import MissionPlan


def _mutate(good: dict, mutator) -> dict:
    mutator(good)
    return good


# ---------------------------------------------------------------------------- #
# Happy path
# ---------------------------------------------------------------------------- #


def test_good_plan_passes_all_wave1_rules(good_plan: MissionPlan):
    report = validate_plan(good_plan)
    assert report.ok, f"unexpected violations: {report.violations}"
    wave1 = {"SEQ-01", "SEQ-02", "SEQ-03"}
    assert wave1 <= {r.rule for r in report.results}  # registry grows with later waves
    assert all(r.passed for r in report.results if r.rule in wave1)


# ---------------------------------------------------------------------------- #
# SEQ-01 — mission shape
# ---------------------------------------------------------------------------- #


def test_seq01_missing_takeoff(good_dict):
    good_dict["steps"] = good_dict["steps"][1:]  # drop takeoff
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    assert "SEQ-01" in report.failed_rules()


def test_seq01_missing_land(good_dict):
    good_dict["steps"] = good_dict["steps"][:-1]  # drop land
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    assert "SEQ-01" in report.failed_rules()


def test_seq01_missing_return_home(good_dict):
    good_dict["steps"] = [s for s in good_dict["steps"] if s["action"] != "return_home"]
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    assert "SEQ-01" in report.failed_rules()


def test_seq01_double_takeoff(good_dict):
    good_dict["steps"].insert(1, {"action": "takeoff", "alt_m": 30.0})
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    msgs = " | ".join(v.message for v in report.violations)
    assert "SEQ-01" in report.failed_rules()
    assert "takeoff" in msgs


def test_seq01_double_land(good_dict):
    good_dict["steps"].append({"action": "land"})
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    assert "SEQ-01" in report.failed_rules()


def test_seq01_violation_carries_step_index(good_dict):
    good_dict["steps"] = good_dict["steps"][1:]  # first step now 'goto'
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    seq01 = [v for v in report.violations if v.rule == "SEQ-01"]
    assert any(v.step == 0 for v in seq01)


# ---------------------------------------------------------------------------- #
# SEQ-02 — counts
# ---------------------------------------------------------------------------- #


def test_seq02_too_many_steps(good_dict):
    hold = {"action": "hold", "duration_s": 1.0}
    # inflate to just over the default 40-step limit (insert before return_home)
    while len(good_dict["steps"]) <= 41:
        good_dict["steps"].insert(-2, dict(hold))
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    assert "SEQ-02" in report.failed_rules()
    v = [x for x in report.violations if x.rule == "SEQ-02"][0]
    assert v.value > v.limit


def test_seq02_too_many_captures(good_dict):
    shot = {"action": "capture_photo", "capture": {"mode": "single", "tag": "spam"}}
    for _ in range(45):  # 45 + orbit's 8 + overhead 1 = 54 > default 40
        good_dict["steps"].insert(-2, dict(shot))
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    assert "SEQ-02" in report.failed_rules()


def test_seq02_orbit_captures_are_counted(good_dict):
    # 360/10 = 36 orbit captures + 1 overhead = 37 <= 40 passes;
    # tighten the limit to 30 and it must fail.
    good_dict["steps"][3]["captures_every_deg"] = 10.0
    good_dict["limits"] = {"max_captures": 30}
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    assert "SEQ-02" in report.failed_rules()


# ---------------------------------------------------------------------------- #
# SEQ-03 — ordering
# ---------------------------------------------------------------------------- #


def test_seq03_goto_after_return_home(good_dict):
    stray = {"action": "goto", "to": {"lat": 36.154, "lon": -95.9929}, "alt_m": 20.0, "speed_ms": 3.0}
    good_dict["steps"].insert(len(good_dict["steps"]) - 1, stray)  # between RTH and land
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    assert "SEQ-03" in report.failed_rules()
    v = [x for x in report.violations if x.rule == "SEQ-03"][0]
    assert v.step == len(plan.steps) - 2


def test_seq03_capture_before_takeoff(good_dict):
    shot = {"action": "capture_photo", "capture": {"mode": "single", "tag": "too_early"}}
    good_dict["steps"].insert(0, shot)
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan)
    # SEQ-01 also fires (first step not takeoff) — SEQ-03 must fire specifically too
    assert "SEQ-03" in report.failed_rules()


def test_seq03_ok_when_work_is_between(good_plan: MissionPlan):
    report = validate_plan(good_plan)
    seq03 = [r for r in report.results if r.rule == "SEQ-03"][0]
    assert seq03.passed


# ---------------------------------------------------------------------------- #
# Evil plans — end-to-end through parse_and_validate (the demo artifact)
# ---------------------------------------------------------------------------- #

EVIL_CASES = [
    # (name, mutator, expected_rule_prefixes)
    ("skip_landing", lambda d: d["steps"].pop(), {"SEQ-01"}),
    ("land_twice", lambda d: d["steps"].append({"action": "land"}), {"SEQ-01"}),
    ("marathon", lambda d: [d["steps"].insert(-2, {"action": "hold", "duration_s": 1.0}) for _ in range(45)], {"SEQ-02"}),
    ("invented_action", lambda d: d["steps"].insert(1, {"action": "strafe_run"}), {"SCHEMA-01"}),
    ("photo_after_home", lambda d: d["steps"].insert(len(d["steps"]) - 1, {"action": "capture_photo", "capture": {"mode": "single", "tag": "late"}}), {"SEQ-03"}),
]


@pytest.mark.parametrize(("name", "mutator", "expected"), EVIL_CASES, ids=[c[0] for c in EVIL_CASES])
def test_evil_plans_die_with_the_right_rule(good_dict, name, mutator, expected):
    mutator(good_dict)
    plan, report = parse_and_validate(good_dict)
    assert not report.ok, f"evil plan '{name}' was approved!"
    fired = set(report.failed_rules())
    assert expected & fired, f"'{name}' should trip {expected}, got {fired}"
