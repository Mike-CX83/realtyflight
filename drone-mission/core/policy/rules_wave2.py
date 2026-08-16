"""Wave 2 — numeric-envelope rules (doc 11 §3, Wave 2).

The schema already enforces ABSOLUTE caps (alt ≤ 120 m, speed ≤ 8 m/s,
radius 8–100 m). These rules enforce the tighter MISSION envelope in
plan.limits — the numbers the operator approved for THIS flight.

GEO-04  every altitude ≤ mission ceiling; takeoff/orbit above their floors
KIN-01  every speed ≤ mission speed cap
KIN-02  orbit radius sane relative to the arrival tolerance
GEO-05  nothing farther from home than the distance cap (orbit worst-point aware)
"""

from __future__ import annotations

from core.geo import distance_m
from core.policy.types import Violation
from core.schema import Goto, MissionPlan, Orbit, Takeoff


def rule_geo_04_altitude(plan: MissionPlan) -> list[Violation]:
    v: list[Violation] = []
    ceiling = plan.limits.max_alt_m
    for i, step in enumerate(plan.steps):
        alt = getattr(step, "alt_m", None)
        if alt is None:
            continue
        if alt > ceiling:
            v.append(
                Violation(
                    rule="GEO-04",
                    step=i,
                    message=f"Step {i} ('{step.action}') altitude {alt:g} m exceeds "
                    f"the mission ceiling {ceiling:g} m.",
                    value=alt,
                    limit=ceiling,
                )
            )
        if isinstance(step, Takeoff) and alt < plan.limits.min_takeoff_alt_m:
            v.append(
                Violation(
                    rule="GEO-04",
                    step=i,
                    message=f"Takeoff altitude {alt:g} m is below the "
                    f"{plan.limits.min_takeoff_alt_m:g} m floor.",
                    value=alt,
                    limit=plan.limits.min_takeoff_alt_m,
                )
            )
        if isinstance(step, Orbit) and alt < plan.limits.min_orbit_alt_m:
            v.append(
                Violation(
                    rule="GEO-04",
                    step=i,
                    message=f"Orbit altitude {alt:g} m is below the "
                    f"{plan.limits.min_orbit_alt_m:g} m floor.",
                    value=alt,
                    limit=plan.limits.min_orbit_alt_m,
                )
            )
    return v


def rule_kin_01_speed(plan: MissionPlan) -> list[Violation]:
    v: list[Violation] = []
    cap = plan.limits.max_speed_ms
    for i, step in enumerate(plan.steps):
        speed = getattr(step, "speed_ms", None)
        if speed is not None and speed > cap:
            v.append(
                Violation(
                    rule="KIN-01",
                    step=i,
                    message=f"Step {i} ('{step.action}') speed {speed:g} m/s exceeds "
                    f"the mission cap {cap:g} m/s.",
                    value=speed,
                    limit=cap,
                )
            )
    return v


def rule_kin_02_orbit_radius(plan: MissionPlan) -> list[Violation]:
    """Radius must dwarf the arrival tolerance, or the waypoint-ring orbit
    degenerates into noise (drone 'arrives' everywhere on the circle at once)."""
    v: list[Violation] = []
    min_radius = 1.5 * plan.limits.acceptance_radius_m
    for i, step in enumerate(plan.steps):
        if not isinstance(step, Orbit):
            continue
        if step.radius_m < min_radius:
            v.append(
                Violation(
                    rule="KIN-02",
                    step=i,
                    message=(
                        f"Orbit radius {step.radius_m:g} m is under 1.5x the arrival tolerance "
                        f"({plan.limits.acceptance_radius_m:g} m); "
                        f"minimum here is {min_radius:g} m."
                    ),
                    value=step.radius_m,
                    limit=min_radius,
                )
            )
    return v


def rule_geo_05_home_distance(plan: MissionPlan) -> list[Violation]:
    """Worst-case horizontal distance from home for every positioned step.
    For orbits the worst point is center-distance + radius."""
    v: list[Violation] = []
    cap = plan.limits.max_home_dist_m
    home = plan.property.home
    for i, step in enumerate(plan.steps):
        if isinstance(step, Goto):
            d = distance_m(home, step.to)
            label = "waypoint"
        elif isinstance(step, Orbit):
            d = distance_m(home, step.center) + step.radius_m
            label = "orbit's farthest point"
        else:
            continue
        if d > cap:
            v.append(
                Violation(
                    rule="GEO-05",
                    step=i,
                    message=f"Step {i}: {label} is {d:.0f} m from home; the cap is {cap:g} m.",
                    value=round(d, 1),
                    limit=cap,
                )
            )
    return v
