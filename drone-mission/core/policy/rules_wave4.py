"""Wave 4 — live-state rules (doc 11 §3, Wave 4).

These are the first rules that read the DRONE, not the plan. They receive a
ValidationContext carrying the latest TelemetrySnapshot, the selected
backend's BackendCapabilities, and the caller's clock (`now_ts` — injected so
rules stay pure and testable; no rule ever reads the wall clock itself).

Deny-by-default is literal here: missing telemetry, missing capabilities, or
stale data is a FAILURE with its own message — never a skipped check
(doc 00 §3.5: "no fake telemetry, fail closed").

PWR-01  battery at/above the preflight floor, read from FRESH telemetry
PWR-02  conservative endurance math: the mission must fit the battery budget
TEL-01  telemetry fresh; GPS ready; link up
CAP-01  every plan step is something the selected backend can actually do
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.geo import distance_m
from core.interfaces import BackendCapabilities, TelemetrySnapshot
from core.policy.types import Violation
from core.schema import CapturePhoto, Goto, Hold, MissionPlan, Orbit, SetGimbal, Takeoff

# Conservative motion model constants for the endurance estimate (PWR-02).
CLIMB_RATE_MS = 1.5
DESCENT_RATE_MS = 1.0
CAPTURE_DWELL_S = 4.0        # settle + shoot (a bracket takes a few seconds)
GIMBAL_MOVE_S = 2.0
TRANSITION_OVERHEAD_S = 2.0  # per step: accel/decel, command latency
MIN_SAT_COUNT = 8            # GPS readiness floor for outdoor missions


@dataclass(frozen=True)
class ValidationContext:
    """Live inputs to the dispatch-gate rules. `now_ts` is the caller's clock."""

    now_ts: float
    telemetry: TelemetrySnapshot | None = None
    capabilities: BackendCapabilities | None = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def estimate_mission_duration_s(plan: MissionPlan) -> float:
    """Deliberately conservative time estimate for the whole mission.

    Tracks position through the steps (starting at home), charges every leg at
    its own speed, climbs/descents at fixed rates, adds capture/gimbal dwell
    and a per-step overhead. Overestimating is fine; underestimating is what
    PWR-02 exists to prevent.
    """
    t = 0.0
    pos = plan.property.home
    alt = 0.0

    for step in plan.steps:
        t += TRANSITION_OVERHEAD_S
        if isinstance(step, Takeoff):
            t += step.alt_m / CLIMB_RATE_MS
            alt = step.alt_m
        elif isinstance(step, Goto):
            t += distance_m(pos, step.to) / step.speed_ms
            t += abs(step.alt_m - alt) / (CLIMB_RATE_MS if step.alt_m > alt else DESCENT_RATE_MS)
            pos, alt = step.to, step.alt_m
        elif isinstance(step, Orbit):
            # transit to the ring, then fly the arc
            join_dist = max(0.0, distance_m(pos, step.center) - step.radius_m)
            t += join_dist / step.speed_ms
            t += abs(step.alt_m - alt) / (CLIMB_RATE_MS if step.alt_m > alt else DESCENT_RATE_MS)
            arc_len = 2.0 * math.pi * step.radius_m * (step.arc_deg / 360.0)
            t += arc_len / step.speed_ms
            if step.captures_every_deg is not None:
                n = max(1, int(step.arc_deg // step.captures_every_deg))
                t += n * CAPTURE_DWELL_S
            pos, alt = step.center, step.alt_m  # ends near the ring; center is close enough
        elif isinstance(step, SetGimbal):
            t += GIMBAL_MOVE_S
        elif isinstance(step, CapturePhoto):
            t += CAPTURE_DWELL_S
        elif isinstance(step, Hold):
            t += step.duration_s
        elif step.action == "return_home":
            t += distance_m(pos, plan.property.home) / plan.limits.max_speed_ms
            pos = plan.property.home
        elif step.action == "land":
            t += alt / DESCENT_RATE_MS
            alt = 0.0
    return t


def _fresh_telemetry(
    ctx: ValidationContext, plan: MissionPlan, rule: str
) -> tuple[TelemetrySnapshot | None, list[Violation]]:
    """Shared deny-by-default gate: telemetry must exist and be fresh."""
    if ctx.telemetry is None:
        return None, [
            Violation(
                rule=rule,
                message="No telemetry available from the selected backend — cannot verify. "
                "Denied by default.",
            )
        ]
    age = ctx.now_ts - ctx.telemetry.ts
    limit = plan.failsafe.telemetry_stale_hold_s
    if age > limit:
        return None, [
            Violation(
                rule=rule,
                message=f"Telemetry is {age:.1f} s old; anything older than {limit:g} s "
                "cannot be trusted for a flight decision. Denied by default.",
                value=round(age, 1),
                limit=limit,
            )
        ]
    if age < 0:
        return None, [
            Violation(
                rule=rule,
                message=f"Telemetry timestamp is {-age:.1f} s in the future — clock skew; "
                "refusing to reason from it.",
                value=round(age, 1),
                limit=0,
            )
        ]
    return ctx.telemetry, []


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #


def rule_pwr_01_battery_floor(plan: MissionPlan, ctx: ValidationContext) -> list[Violation]:
    tel, v = _fresh_telemetry(ctx, plan, "PWR-01")
    if tel is None:
        return v
    floor = plan.failsafe.battery_floor_pct
    if tel.battery_pct < floor:
        v.append(
            Violation(
                rule="PWR-01",
                message=f"Battery {tel.battery_pct:g}% is below the {floor:g}% preflight floor.",
                value=tel.battery_pct,
                limit=floor,
            )
        )
    return v


def rule_pwr_02_endurance(plan: MissionPlan, ctx: ValidationContext) -> list[Violation]:
    v: list[Violation] = []
    if ctx.capabilities is None:
        return [
            Violation(
                rule="PWR-02",
                message="No backend capabilities available — cannot verify endurance. "
                "Denied by default.",
            )
        ]
    tel, tv = _fresh_telemetry(ctx, plan, "PWR-02")
    if tel is None:
        return tv

    est_min = estimate_mission_duration_s(plan) / 60.0
    usable_fraction = max(0.0, tel.battery_pct - plan.failsafe.battery_reserve_pct) / 100.0
    available_min = ctx.capabilities.endurance_min_conservative * usable_fraction

    if est_min > available_min:
        v.append(
            Violation(
                rule="PWR-02",
                message=(
                    f"Estimated mission time {est_min:.1f} min exceeds the usable battery budget "
                    f"{available_min:.1f} min (endurance "
                    f"{ctx.capabilities.endurance_min_conservative:g} min "
                    f"x battery {tel.battery_pct:g}% minus "
                    f"{plan.failsafe.battery_reserve_pct:g}% reserve)."
                ),
                value=round(est_min, 1),
                limit=round(available_min, 1),
            )
        )
    return v


def rule_tel_01_readiness(plan: MissionPlan, ctx: ValidationContext) -> list[Violation]:
    tel, v = _fresh_telemetry(ctx, plan, "TEL-01")
    if tel is None:
        return v
    if not tel.link_ok:
        v.append(Violation(rule="TEL-01", message="Command/telemetry link is down."))
    if not tel.gps_ok:
        v.append(Violation(rule="TEL-01", message="GPS is not ready (no usable fix)."))
    elif tel.sat_count is not None and tel.sat_count < MIN_SAT_COUNT:
        v.append(
            Violation(
                rule="TEL-01",
                message=f"Only {tel.sat_count} GPS satellites; need at least {MIN_SAT_COUNT} "
                "for an outdoor mission.",
                value=tel.sat_count,
                limit=MIN_SAT_COUNT,
            )
        )
    return v


def rule_cap_01_backend_supports_plan(plan: MissionPlan, ctx: ValidationContext) -> list[Violation]:
    caps = ctx.capabilities
    if caps is None:
        return [
            Violation(
                rule="CAP-01",
                message="No backend capabilities available — cannot verify the plan is flyable "
                "on this aircraft. Denied by default.",
            )
        ]

    v: list[Violation] = []
    for i, step in enumerate(plan.steps):
        if isinstance(step, Takeoff) and step.alt_m < caps.min_takeoff_alt_m:
            v.append(
                Violation(
                    rule="CAP-01",
                    step=i,
                    message=f"Backend '{caps.name}' cannot take off below "
                    f"{caps.min_takeoff_alt_m:g} m (plan asks {step.alt_m:g} m).",
                    value=step.alt_m,
                    limit=caps.min_takeoff_alt_m,
                )
            )
        elif isinstance(step, SetGimbal) and not caps.supports_gimbal_pitch:
            v.append(
                Violation(
                    rule="CAP-01",
                    step=i,
                    message=f"Backend '{caps.name}' has no controllable gimbal; "
                    "remove set_gimbal steps.",
                )
            )
        elif isinstance(step, CapturePhoto) and step.capture.mode not in caps.supports_bracketing:
            v.append(
                Violation(
                    rule="CAP-01",
                    step=i,
                    message=f"Backend '{caps.name}' does not support capture mode "
                    f"'{step.capture.mode}' (supported: {sorted(caps.supports_bracketing)}). "
                    "No silent downgrade — change the plan.",
                    value=step.capture.mode,
                )
            )
        elif isinstance(step, Orbit) and step.capture is not None:
            if step.capture.mode not in caps.supports_bracketing:
                v.append(
                    Violation(
                        rule="CAP-01",
                        step=i,
                        message=f"Backend '{caps.name}' does not support orbit capture mode "
                        f"'{step.capture.mode}' (supported: {sorted(caps.supports_bracketing)}).",
                        value=step.capture.mode,
                    )
                )
    return v
