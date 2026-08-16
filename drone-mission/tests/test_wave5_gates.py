"""Wave-5 tests: approvals, the sim/real wall, and the dispatch gate.
These encode the governance story end-to-end: nothing flies without a fresh,
hash-bound, live-checked, profile-matched human yes — and the breaker beats
everything."""

from __future__ import annotations

import dataclasses

import pytest

from core.approval import (
    APPROVAL_TTL_S,
    REAL_FLIGHT_CONFIRMATION,
    ApprovalError,
    grant_approval,
)
from core.policy import ValidationContext
from core.policy.dispatch import CircuitBreaker, DispatchContext, check_dispatch
from core.policy.engine import validate_plan
from core.schema import MissionPlan
from tests.conftest import NOW


def _approved(good_plan, good_ctx, *, profile="sim", typed=None):
    report = validate_plan(good_plan, good_ctx)
    return grant_approval(
        good_plan, report, operator="mike", now_ts=NOW, profile=profile, typed_confirmation=typed
    )


def _dctx(good_ctx, approval, *, now_ts=NOW + 5.0, profile="sim") -> DispatchContext:
    return DispatchContext(now_ts=now_ts, profile=profile, approval=approval, live=good_ctx)


# ---------------------------------------------------------------------------- #
# grant_approval — the only door in
# ---------------------------------------------------------------------------- #


def test_grant_refuses_static_only_report(good_plan):
    static_report = validate_plan(good_plan)  # no live context
    with pytest.raises(ApprovalError, match="static-only"):
        grant_approval(good_plan, static_report, operator="mike", now_ts=NOW)


def test_grant_refuses_failing_report(good_dict, good_ctx):
    good_dict["steps"][3]["alt_m"] = 100.0  # GEO-04 violation
    plan = MissionPlan.model_validate(good_dict)
    report = validate_plan(plan, good_ctx)
    with pytest.raises(ApprovalError, match="GEO-04"):
        grant_approval(plan, report, operator="mike", now_ts=NOW)


def test_grant_happy_path_binds_hash(good_plan, good_ctx):
    a = _approved(good_plan, good_ctx)
    from core.schema import compute_plan_hash

    assert a.plan_hash == compute_plan_hash(good_plan)
    assert a.profile == "sim" and a.real_confirmed is False
    assert a.mission_id == good_plan.mission_id


def test_grant_real_requires_exact_phrase(good_plan, good_ctx):
    with pytest.raises(ApprovalError, match="confirmation phrase"):
        _approved(good_plan, good_ctx, profile="real", typed="yes I'm sure")
    with pytest.raises(ApprovalError, match="confirmation phrase"):
        _approved(good_plan, good_ctx, profile="real", typed=None)
    a = _approved(good_plan, good_ctx, profile="real", typed=REAL_FLIGHT_CONFIRMATION)
    assert a.real_confirmed is True


# ---------------------------------------------------------------------------- #
# APR-01 — hash binding, expiry, mission identity
# ---------------------------------------------------------------------------- #


def test_apr01_clean_dispatch_passes(good_plan, good_ctx):
    a = _approved(good_plan, good_ctx)
    violations = check_dispatch(good_plan, _dctx(good_ctx, a))
    assert violations == [], [v.message for v in violations]


def test_apr01_no_approval(good_plan, good_ctx):
    violations = check_dispatch(good_plan, _dctx(good_ctx, None))
    assert any(v.rule == "APR-01" and "No approval" in v.message for v in violations)


def test_apr01_edit_after_approval_voids_it(good_dict, good_ctx):
    plan = MissionPlan.model_validate(good_dict)
    a = _approved(plan, good_ctx)
    good_dict["steps"][0]["alt_m"] = 26.0  # one meter higher, after approval
    edited = MissionPlan.model_validate(good_dict)
    violations = check_dispatch(edited, _dctx(good_ctx, a))
    assert any(v.rule == "APR-01" and "hash mismatch" in v.message for v in violations)


def test_apr01_expires_unused(good_plan, good_ctx):
    a = _approved(good_plan, good_ctx)
    late = NOW + APPROVAL_TTL_S + 1.0
    _stale_live = dataclasses.replace(good_ctx)  # telemetry ts fixed at NOW-0.5...
    violations = check_dispatch(good_plan, _dctx(good_ctx, a, now_ts=late))
    assert any(v.rule == "APR-01" and "expired" in v.message for v in violations)


def test_apr01_activation_stops_expiry(good_plan, good_ctx):
    a = _approved(good_plan, good_ctx).activated(NOW + 10.0)  # first dispatch at +10 s
    assert a.is_expired(NOW + APPROVAL_TTL_S + 100.0) is False


def test_apr01_wrong_mission(good_plan, good_dict, good_ctx):
    a = _approved(good_plan, good_ctx)
    good_dict["mission_id"] = "01DIFFERENTMISSION00000000"
    other = MissionPlan.model_validate(good_dict)
    violations = check_dispatch(other, _dctx(good_ctx, a))
    assert any(v.rule == "APR-01" and "belongs to mission" in v.message for v in violations)


# ---------------------------------------------------------------------------- #
# ENV-01 — the sim/real wall
# ---------------------------------------------------------------------------- #


def _physical_ctx(good_ctx) -> ValidationContext:
    phys = good_ctx.capabilities.model_copy(update={"name": "anafi_ai", "is_physical": True})
    return dataclasses.replace(good_ctx, capabilities=phys)


def test_env01_sim_profile_cannot_touch_physical(good_plan, good_ctx):
    phys_live = _physical_ctx(good_ctx)
    a = _approved(good_plan, phys_live)  # sim-profile approval
    dctx = DispatchContext(now_ts=NOW + 5, profile="sim", approval=a, live=phys_live)
    violations = check_dispatch(good_plan, dctx)
    assert any(v.rule == "ENV-01" and "PHYSICAL" in v.message for v in violations)


def test_env01_physical_needs_confirmed_approval(good_plan, good_ctx):
    phys_live = _physical_ctx(good_ctx)
    a = _approved(good_plan, phys_live)  # granted WITHOUT the typed phrase (sim profile)
    dctx = DispatchContext(now_ts=NOW + 5, profile="real", approval=a, live=phys_live)
    violations = check_dispatch(good_plan, dctx)
    assert any(v.rule == "ENV-01" and "typed" in v.message for v in violations)
    assert any(v.rule == "ENV-01" and "must match" in v.message for v in violations)


def test_env01_full_real_flow_passes(good_plan, good_ctx):
    phys_live = _physical_ctx(good_ctx)
    a = _approved(good_plan, phys_live, profile="real", typed=REAL_FLIGHT_CONFIRMATION)
    dctx = DispatchContext(now_ts=NOW + 5, profile="real", approval=a, live=phys_live)
    violations = check_dispatch(good_plan, dctx)
    assert violations == [], [v.message for v in violations]


def test_env01_profile_mismatch_even_in_sim(good_plan, good_ctx):
    a = _approved(good_plan, good_ctx, profile="sim")
    dctx = DispatchContext(now_ts=NOW + 5, profile="real", approval=a, live=good_ctx)
    violations = check_dispatch(good_plan, dctx)
    assert any(v.rule == "ENV-01" and "must match" in v.message for v in violations)


# ---------------------------------------------------------------------------- #
# The circuit breaker — beats everything
# ---------------------------------------------------------------------------- #


def test_breaker_open_blocks_even_perfect_dispatch(good_plan, good_ctx):
    a = _approved(good_plan, good_ctx)
    breaker = CircuitBreaker()
    breaker.trip("operator hit the kill switch")
    violations = check_dispatch(good_plan, _dctx(good_ctx, a), breaker)
    assert any(v.rule == "CB-01" and "OPEN" in v.message for v in violations)


def test_breaker_requires_explicit_human_reset(good_plan, good_ctx):
    breaker = CircuitBreaker()
    breaker.trip("test trip")
    assert breaker.is_open
    breaker.reset(operator="mike")
    assert not breaker.is_open
    assert breaker.trip_log == ["test trip", "reset by mike"]


def test_dispatch_gate_rechecks_reality(good_plan, good_ctx):
    """Approval was granted on a healthy drone; battery then crashed. The gate
    must catch it — approval is a snapshot, reality moves."""
    from core.interfaces import TelemetrySnapshot
    from tests.conftest import good_telemetry_dict

    a = _approved(good_plan, good_ctx)  # granted at 95% battery
    dying = TelemetrySnapshot.model_validate(
        good_telemetry_dict(battery_pct=18.0, ts=NOW + 4.8)
    )
    live_now = dataclasses.replace(good_ctx, now_ts=NOW + 5.0, telemetry=dying)
    dctx = DispatchContext(now_ts=NOW + 5.0, profile="sim", approval=a, live=live_now)
    violations = check_dispatch(good_plan, dctx)
    assert any(v.rule == "PWR-01" for v in violations)
