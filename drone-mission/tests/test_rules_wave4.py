"""Wave-4 rule tests: live drone state. The deny-by-default cases (missing or
stale telemetry) are the most important tests in this file — they encode the
project's core safety stance."""

from __future__ import annotations

import dataclasses

import pytest

from core.interfaces import TelemetrySnapshot
from core.policy import ValidationContext
from core.policy.engine import validate_plan
from core.policy.rules_wave4 import estimate_mission_duration_s
from core.schema import MissionPlan
from tests.conftest import NOW, good_telemetry_dict


def _tel(**overrides) -> TelemetrySnapshot:
    return TelemetrySnapshot.model_validate(good_telemetry_dict(**overrides))


def _ctx_with(ctx: ValidationContext, **changes) -> ValidationContext:
    return dataclasses.replace(ctx, **changes)


# ---------------------------------------------------------------------------- #
# Static vs live reports
# ---------------------------------------------------------------------------- #


def test_static_report_is_not_live(good_plan: MissionPlan):
    report = validate_plan(good_plan)  # no context
    assert report.live_checked is False
    assert not any(r.rule.startswith(("PWR", "TEL", "CAP")) for r in report.results)


def test_live_report_runs_all_eleven_rules(good_plan: MissionPlan, good_ctx):
    report = validate_plan(good_plan, good_ctx)
    assert report.live_checked is True
    assert report.ok, f"unexpected violations: {report.violations}"
    assert {r.rule for r in report.results} == {
        "SEQ-01", "SEQ-02", "SEQ-03",
        "GEO-04", "KIN-01", "KIN-02", "GEO-05",
        "GEO-01", "GEO-02", "GEO-03",
        "PWR-01", "PWR-02", "TEL-01", "CAP-01",
    }


# ---------------------------------------------------------------------------- #
# Deny-by-default: missing / stale / time-skewed state
# ---------------------------------------------------------------------------- #


def test_missing_telemetry_denies(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=None)
    report = validate_plan(good_plan, ctx)
    assert {"PWR-01", "PWR-02", "TEL-01"} <= set(report.failed_rules())
    assert any("Denied by default" in v.message for v in report.violations)


def test_missing_capabilities_denies(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, capabilities=None)
    report = validate_plan(good_plan, ctx)
    assert {"PWR-02", "CAP-01"} <= set(report.failed_rules())


def test_stale_telemetry_denies(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=_tel(ts=NOW - 5.0))  # 5 s old > 2 s hold limit
    report = validate_plan(good_plan, ctx)
    assert {"PWR-01", "TEL-01"} <= set(report.failed_rules())
    v = [x for x in report.violations if x.rule == "TEL-01"][0]
    assert v.value == 5.0 and v.limit == 2.0


def test_future_timestamp_denies(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=_tel(ts=NOW + 30.0))  # clock skew
    report = validate_plan(good_plan, ctx)
    assert "TEL-01" in report.failed_rules()
    assert any("future" in v.message for v in report.violations)


# ---------------------------------------------------------------------------- #
# PWR-01 — battery floor
# ---------------------------------------------------------------------------- #


def test_pwr01_battery_below_floor(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=_tel(battery_pct=25.0))  # floor is 30
    report = validate_plan(good_plan, ctx)
    v = [x for x in report.violations if x.rule == "PWR-01"][0]
    assert v.value == 25.0 and v.limit == 30.0


def test_pwr01_battery_at_floor_passes(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=_tel(battery_pct=30.0))
    report = validate_plan(good_plan, ctx)
    assert [r for r in report.results if r.rule == "PWR-01"][0].passed


# ---------------------------------------------------------------------------- #
# PWR-02 — endurance budget
# ---------------------------------------------------------------------------- #


def test_estimate_is_sane_for_fixture(good_plan):
    est = estimate_mission_duration_s(good_plan)
    # fixture: takeoff 25m, ~70m goto, 20m-radius orbit w/ 8 captures, climb, RTH...
    assert 120 < est < 600  # minutes-scale, not seconds or hours


def test_estimate_grows_with_more_work(good_dict):
    base = estimate_mission_duration_s(MissionPlan.model_validate(good_dict))
    good_dict["steps"].insert(-2, {"action": "hold", "duration_s": 60.0})
    longer = estimate_mission_duration_s(MissionPlan.model_validate(good_dict))
    assert longer == pytest.approx(base + 60.0 + 2.0, abs=0.1)  # +hold +overhead


def test_pwr02_tiny_endurance_fails(good_plan, good_ctx):
    weak = good_ctx.capabilities.model_copy(update={"endurance_min_conservative": 3.0})
    ctx = _ctx_with(good_ctx, capabilities=weak)
    report = validate_plan(good_plan, ctx)
    assert "PWR-02" in report.failed_rules()


def test_pwr02_low_battery_shrinks_budget(good_plan, good_ctx):
    # 32% battery minus 20% reserve = 12% of 20 min = 2.4 min budget < mission
    ctx = _ctx_with(good_ctx, telemetry=_tel(battery_pct=32.0))
    report = validate_plan(good_plan, ctx)
    v = [x for x in report.violations if x.rule == "PWR-02"][0]
    assert v.limit == pytest.approx(2.4, abs=0.1)


def test_pwr02_healthy_battery_passes(good_plan, good_ctx):
    report = validate_plan(good_plan, good_ctx)  # 95% battery, 20 min endurance
    assert [r for r in report.results if r.rule == "PWR-02"][0].passed


# ---------------------------------------------------------------------------- #
# TEL-01 — readiness
# ---------------------------------------------------------------------------- #


def test_tel01_link_down(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=_tel(link_ok=False))
    report = validate_plan(good_plan, ctx)
    assert any(v.rule == "TEL-01" and "link" in v.message.lower() for v in report.violations)


def test_tel01_no_gps_fix(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=_tel(gps_ok=False))
    report = validate_plan(good_plan, ctx)
    assert any(v.rule == "TEL-01" and "GPS" in v.message for v in report.violations)


def test_tel01_too_few_satellites(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=_tel(sat_count=5))
    report = validate_plan(good_plan, ctx)
    v = [x for x in report.violations if x.rule == "TEL-01"][0]
    assert v.value == 5 and v.limit == 8


def test_tel01_unknown_satcount_with_fix_passes(good_plan, good_ctx):
    ctx = _ctx_with(good_ctx, telemetry=_tel(sat_count=None))
    report = validate_plan(good_plan, ctx)
    assert [r for r in report.results if r.rule == "TEL-01"][0].passed


# ---------------------------------------------------------------------------- #
# CAP-01 — backend supports the plan
# ---------------------------------------------------------------------------- #


def test_cap01_bracket_unsupported(good_plan, good_ctx):
    basic = good_ctx.capabilities.model_copy(
        update={"supports_bracketing": frozenset({"single"})}
    )
    ctx = _ctx_with(good_ctx, capabilities=basic)
    report = validate_plan(good_plan, ctx)  # fixture orbit uses bracket3
    v = [x for x in report.violations if x.rule == "CAP-01"][0]
    assert (v.value == "bracket3" and "No silent downgrade" in v.message) or (
        "not support" in v.message
    )


def test_cap01_no_gimbal(good_plan, good_ctx):
    nogimbal = good_ctx.capabilities.model_copy(update={"supports_gimbal_pitch": False})
    ctx = _ctx_with(good_ctx, capabilities=nogimbal)
    report = validate_plan(good_plan, ctx)  # fixture has two set_gimbal steps
    hits = [v for v in report.violations if v.rule == "CAP-01"]
    assert len(hits) >= 2


def test_cap01_takeoff_below_backend_minimum(good_dict, good_ctx):
    highmin = good_ctx.capabilities.model_copy(update={"min_takeoff_alt_m": 30.0})
    ctx = _ctx_with(good_ctx, capabilities=highmin)
    report = validate_plan(MissionPlan.model_validate(good_dict), ctx)  # takeoff 25 < 30
    assert any(v.rule == "CAP-01" and v.step == 0 for v in report.violations)


def test_cap01_full_capabilities_pass(good_plan, good_ctx):
    report = validate_plan(good_plan, good_ctx)
    assert [r for r in report.results if r.rule == "CAP-01"][0].passed


# ---------------------------------------------------------------------------- #
# Evil scenarios, Wave-4 edition — the operator tries to fly anyway
# ---------------------------------------------------------------------------- #

EVIL_CASES = [
    ("dead_battery_launch", {"battery_pct": 12.0}, {"PWR-01", "PWR-02"}),
    ("yesterdays_data", {"ts": NOW - 86_400.0}, {"PWR-01", "PWR-02", "TEL-01"}),
    ("no_gps_in_the_yard", {"gps_ok": False, "sat_count": 0}, {"TEL-01"}),
    ("link_already_dead", {"link_ok": False}, {"TEL-01"}),
]


@pytest.mark.parametrize(
    ("name", "tel_overrides", "expected"), EVIL_CASES, ids=[c[0] for c in EVIL_CASES]
)
def test_wave4_evil_states_deny(good_plan, good_ctx, name, tel_overrides, expected):
    ctx = _ctx_with(good_ctx, telemetry=_tel(**tel_overrides))
    report = validate_plan(good_plan, ctx)
    assert not report.ok, f"'{name}' was approved!"
    fired = set(report.failed_rules())
    assert expected <= fired, f"'{name}' should trip at least {expected}, got {fired}"
