"""Wave 3 — boundary-geometry rules (doc 11 §3, Wave 3).

All math happens in the LocalFrame meters plane centered on home (Shapely is
planar). Constants below are structural safety choices (doc 08 §4), not
per-mission knobs — changing them is an architecture decision, not a config
edit, which is why they live here with names and comments.

GEO-01  boundary polygon is sane (valid ring, no self-intersection, sensible area)
GEO-02  home lies inside the boundary with margin
GEO-03  every waypoint and every orbit ring stays inside the boundary shrunk
        by the safety margin
"""

from __future__ import annotations

from shapely.geometry import Polygon
from shapely.validation import explain_validity

from core.geo import LocalFrame
from core.policy.types import Violation
from core.schema import Goto, MissionPlan, Orbit

# Structural constants (doc 08 §4 rule catalog)
MIN_BOUNDARY_AREA_M2 = 100.0        # smaller than a shed's yard => operator error
MAX_BOUNDARY_AREA_M2 = 250_000.0    # 0.25 km2 => bigger than any residential lot
HOME_MARGIN_M = 2.0                 # home must not sit ON the fence line
BOUNDARY_SAFETY_MARGIN_M = 3.0      # flight keeps 3 m inside the drawn fence


def _frame_and_polygon(plan: MissionPlan) -> tuple[LocalFrame, Polygon]:
    frame = LocalFrame(plan.property.home)
    return frame, frame.polygon(plan.property.boundary)


def rule_geo_01_boundary_valid(plan: MissionPlan) -> list[Violation]:
    v: list[Violation] = []
    _frame, poly = _frame_and_polygon(plan)

    if not poly.is_valid:
        v.append(
            Violation(
                rule="GEO-01",
                message=f"Boundary polygon is invalid: {explain_validity(poly)}. "
                "Redraw it without crossing edges.",
            )
        )
        return v  # area of an invalid polygon is meaningless

    area = poly.area
    if area < MIN_BOUNDARY_AREA_M2:
        v.append(
            Violation(
                rule="GEO-01",
                message=f"Boundary area {area:.0f} m² is below the {MIN_BOUNDARY_AREA_M2:.0f} m² minimum.",
                value=round(area, 1),
                limit=MIN_BOUNDARY_AREA_M2,
            )
        )
    if area > MAX_BOUNDARY_AREA_M2:
        v.append(
            Violation(
                rule="GEO-01",
                message=f"Boundary area {area:.0f} m² exceeds the {MAX_BOUNDARY_AREA_M2:.0f} m² "
                "maximum (0.25 km²) — that is not a residential property.",
                value=round(area, 1),
                limit=MAX_BOUNDARY_AREA_M2,
            )
        )
    return v


def rule_geo_02_home_inside(plan: MissionPlan) -> list[Violation]:
    frame, poly = _frame_and_polygon(plan)
    if not poly.is_valid:
        return [
            Violation(
                rule="GEO-02",
                message="Cannot verify home position: boundary polygon is invalid (see GEO-01).",
            )
        ]

    interior = poly.buffer(-HOME_MARGIN_M)
    if interior.is_empty:
        return [
            Violation(
                rule="GEO-02",
                message=f"Boundary is too small to contain a home point with a "
                f"{HOME_MARGIN_M:g} m margin.",
                limit=HOME_MARGIN_M,
            )
        ]

    home_pt = frame.point(plan.property.home)  # (0,0) by construction
    if not home_pt.within(interior):
        dist_to_edge = poly.exterior.distance(home_pt) if poly.contains(home_pt) else -1.0
        return [
            Violation(
                rule="GEO-02",
                message=(
                    f"Home must be inside the boundary with a {HOME_MARGIN_M:g} m margin "
                    + (
                        f"(it is inside but only {dist_to_edge:.1f} m from the fence line)."
                        if dist_to_edge >= 0
                        else "(it is outside the boundary)."
                    )
                ),
                value=round(dist_to_edge, 1) if dist_to_edge >= 0 else "outside",
                limit=HOME_MARGIN_M,
            )
        ]
    return []


def rule_geo_03_flight_inside(plan: MissionPlan) -> list[Violation]:
    """Waypoints and orbit rings stay inside the boundary shrunk by 3 m.
    Orbit is checked as a ring (annulus) of radius ± acceptance tolerance —
    the actual corridor the aircraft occupies while circling."""
    frame, poly = _frame_and_polygon(plan)
    if not poly.is_valid:
        return [
            Violation(
                rule="GEO-03",
                message="Cannot verify flight containment: boundary polygon is invalid (see GEO-01).",
            )
        ]

    safe_zone = poly.buffer(-BOUNDARY_SAFETY_MARGIN_M)
    if safe_zone.is_empty:
        return [
            Violation(
                rule="GEO-03",
                message=f"Boundary is too small to fly in: shrinking it by the "
                f"{BOUNDARY_SAFETY_MARGIN_M:g} m safety margin leaves no room.",
                limit=BOUNDARY_SAFETY_MARGIN_M,
            )
        ]

    v: list[Violation] = []
    acc = plan.limits.acceptance_radius_m
    for i, step in enumerate(plan.steps):
        if isinstance(step, Goto):
            pt = frame.point(step.to)
            if not pt.within(safe_zone):
                v.append(
                    Violation(
                        rule="GEO-03",
                        step=i,
                        message=f"Step {i}: waypoint is outside the boundary "
                        f"(3 m safety margin applied).",
                    )
                )
        elif isinstance(step, Orbit):
            center = frame.point(step.center)
            outer = center.buffer(step.radius_m + acc)
            inner = center.buffer(max(0.0, step.radius_m - acc))
            ring = outer.difference(inner)
            if not ring.within(safe_zone):
                v.append(
                    Violation(
                        rule="GEO-03",
                        step=i,
                        message=(
                            f"Step {i}: the orbit ring (radius {step.radius_m:g} m "
                            f"± {acc:g} m tolerance) leaves the boundary "
                            f"(3 m safety margin applied). Shrink the radius or move the center."
                        ),
                        value=step.radius_m,
                    )
                )
    return v
