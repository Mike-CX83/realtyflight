"""SCHEMA-01: the parser is the first wall. Unknown actions, extra fields,
and out-of-range values must never survive into a MissionPlan object."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.policy.engine import parse_and_validate
from core.schema import MissionPlan, compute_plan_hash


def test_good_plan_parses(good_dict):
    plan = MissionPlan.model_validate(good_dict)
    assert plan.steps[0].action == "takeoff"
    assert plan.expected_capture_count() == 9  # 8 orbit captures + 1 overhead


def test_unknown_action_rejected(good_dict):
    good_dict["steps"].insert(1, {"action": "barrel_roll", "style": "aggressive"})
    with pytest.raises(ValidationError):
        MissionPlan.model_validate(good_dict)


def test_extra_field_rejected(good_dict):
    good_dict["steps"][0]["turbo"] = True
    with pytest.raises(ValidationError):
        MissionPlan.model_validate(good_dict)


def test_extra_top_level_field_rejected(good_dict):
    good_dict["override_safety"] = True
    with pytest.raises(ValidationError):
        MissionPlan.model_validate(good_dict)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("steps", 0, "alt_m"), 200.0),        # above absolute 120 m cap
        (("steps", 0, "alt_m"), 0.0),          # non-positive altitude
        (("steps", 3, "radius_m"), 2.0),       # orbit radius below 8 m floor
        (("steps", 3, "speed_ms"), 30.0),      # orbit speed above cap
        (("limits", "max_alt_m"), 500.0),      # envelope above legal ceiling
        (("property", "boundary"), []),        # empty boundary
        (("steps", 6, "capture", "tag"), "BAD TAG!"),  # tag pattern violation
    ],
)
def test_out_of_range_values_rejected(good_dict, path, value):
    node = good_dict
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValidationError):
        MissionPlan.model_validate(good_dict)


def test_malformed_json_reports_schema01():
    plan, report = parse_and_validate("{not json at all")
    assert plan is None
    assert report.schema_ok is False
    assert report.ok is False
    assert "SCHEMA-01" in report.failed_rules()


def test_schema_failure_names_the_field(good_dict):
    good_dict["steps"][0]["alt_m"] = 999
    plan, report = parse_and_validate(good_dict)
    assert plan is None and not report.ok
    assert any("alt_m" in v.message for v in report.violations)


def test_plan_hash_changes_on_any_edit(good_dict):
    h1 = compute_plan_hash(MissionPlan.model_validate(good_dict))
    good_dict["steps"][0]["alt_m"] = 24.0  # one meter difference
    h2 = compute_plan_hash(MissionPlan.model_validate(good_dict))
    assert h1 != h2


def test_plan_hash_stable_for_same_content(good_dict):
    a = compute_plan_hash(MissionPlan.model_validate(good_dict))
    b = compute_plan_hash(MissionPlan.model_validate(good_dict))
    assert a == b
