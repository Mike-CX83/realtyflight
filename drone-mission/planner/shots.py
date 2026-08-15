"""Shot library v1 — named real-estate photography patterns (roadmap 09 M3).

A "shot" is a small deterministic function: (property, params) -> list of
typed MissionSteps. The library gives missions a shared photographic
vocabulary — front_34_elevated, exterior_orbit, rear_elevated, lot_overhead —
with the craft (bearings, standoff distances, gimbal pitch aimed at the
structure) COMPUTED from geometry instead of guessed per mission.

Two consumers, deliberately different in authority:
- The planner's SYSTEM_PROMPT teaches the LLM these package shapes and
  canonical tags, so live plans converge to the same patterns. The library
  carries NO safety authority — every emitted step still faces the full
  validator like any other step.
- Deterministic callers (tests, the demo's scripted model, later the
  dashboard's one-click packages) compile them directly via
  exterior_package() / compile_mission().

Conventions (v1):
- "front" = the structure side facing the home/launch point: the operator
  parks at the street and launches from it. A real orientation pin arrives
  with the dashboard's map later; this is the honest v1 approximation.
- Bearings are compass degrees: 0 = north, clockwise. Local small-angle
  meter math, same approximation the executor's orbit compiler uses; the
  GEO boundary rules remain the actual safety authority.
"""

from __future__ import annotations

import math

from core.schema import (
    CapturePhoto,
    CaptureSpec,
    Goto,
    Land,
    MissionStep,
    Orbit,
    Property,
    ReturnHome,
    SetGimbal,
    Takeoff,
)

M_PER_DEG_LAT = 111_195.0

# What the gimbal aims at: roughly mid-height of a 1-2 story structure.
TARGET_ALT_M = 4.0


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #


def bearing_deg(frm, to) -> float:
    """Compass bearing (0 = north, cw) from one GeoPoint toward another."""
    north = (to.lat - frm.lat) * M_PER_DEG_LAT
    east = (to.lon - frm.lon) * M_PER_DEG_LAT * math.cos(math.radians(frm.lat))
    return math.degrees(math.atan2(east, north)) % 360.0


def offset(frm, bearing: float, dist_m: float):
    """The GeoPoint `dist_m` meters from `frm` along compass `bearing`."""
    from core.schema import GeoPoint

    rad = math.radians(bearing)
    dlat = (dist_m * math.cos(rad)) / M_PER_DEG_LAT
    dlon = (dist_m * math.sin(rad)) / (M_PER_DEG_LAT * math.cos(math.radians(frm.lat)))
    return GeoPoint(lat=frm.lat + dlat, lon=frm.lon + dlon)


def aim_pitch_deg(alt_m: float, dist_m: float, target_alt_m: float = TARGET_ALT_M) -> float:
    """Gimbal pitch that points the camera from (alt, dist) at the structure's
    mid-height. Negative = down. Clamped to the schema's [-90, 10] envelope."""
    pitch = -math.degrees(math.atan2(alt_m - target_alt_m, max(dist_m, 1.0)))
    return max(-90.0, min(10.0, pitch))


# --------------------------------------------------------------------------- #
# The shots
# --------------------------------------------------------------------------- #


def front_elevated_34(
    prop: Property,
    *,
    alt_m: float = 18.0,
    dist_m: float = 25.0,
    offset_deg: float = 35.0,
    tag: str = "front_34_elevated",
) -> list[MissionStep]:
    """The classic listing hero shot: elevated, from the front, ~35 degrees off
    the front axis so two facades show (the "3/4 view")."""
    front = bearing_deg(prop.center, prop.home)  # front = the home/street side
    pos = offset(prop.center, (front + offset_deg) % 360.0, dist_m)
    return [
        Goto(action="goto", to=pos, alt_m=alt_m, speed_ms=4.0,
             yaw_deg=bearing_deg(pos, prop.center)),
        SetGimbal(action="set_gimbal", pitch_deg=aim_pitch_deg(alt_m, dist_m)),
        CapturePhoto(action="capture_photo",
                     capture=CaptureSpec(mode="bracket3", tag=tag)),
    ]


def rear_elevated(
    prop: Property,
    *,
    alt_m: float = 18.0,
    dist_m: float = 25.0,
    tag: str = "rear_elevated",
) -> list[MissionStep]:
    """Same recipe from the back of the property (yards sell houses)."""
    rear = (bearing_deg(prop.center, prop.home) + 180.0) % 360.0
    pos = offset(prop.center, rear, dist_m)
    return [
        Goto(action="goto", to=pos, alt_m=alt_m, speed_ms=4.0,
             yaw_deg=bearing_deg(pos, prop.center)),
        SetGimbal(action="set_gimbal", pitch_deg=aim_pitch_deg(alt_m, dist_m)),
        CapturePhoto(action="capture_photo",
                     capture=CaptureSpec(mode="bracket3", tag=tag)),
    ]


def exterior_orbit(
    prop: Property,
    *,
    radius_m: float = 20.0,
    alt_m: float = 22.0,
    captures_every_deg: float = 45.0,
    tag: str = "exterior_orbit",
) -> list[MissionStep]:
    """Full 360 around the structure, camera on it the whole way, one bracketed
    capture every N degrees — the orbit package's core."""
    return [
        SetGimbal(action="set_gimbal", pitch_deg=aim_pitch_deg(alt_m, radius_m)),
        Orbit(action="orbit", center=prop.center, radius_m=radius_m, alt_m=alt_m,
              speed_ms=3.0, arc_deg=360.0, direction="cw",
              captures_every_deg=captures_every_deg,
              capture=CaptureSpec(mode="bracket3", tag=tag)),
    ]


def lot_overhead(
    prop: Property,
    *,
    alt_m: float = 38.0,
    tag: str = "lot_overhead",
) -> list[MissionStep]:
    """Straight-down lot/site shot from high over the structure center."""
    return [
        Goto(action="goto", to=prop.center, alt_m=alt_m, speed_ms=3.0, yaw_deg=None),
        SetGimbal(action="set_gimbal", pitch_deg=-90.0),
        CapturePhoto(action="capture_photo",
                     capture=CaptureSpec(mode="single", tag=tag)),
    ]


# Named catalog for programmatic consumers (dashboard one-click packages later).
CATALOG = {
    "front_34_elevated": front_elevated_34,
    "rear_elevated": rear_elevated,
    "exterior_orbit": exterior_orbit,
    "lot_overhead": lot_overhead,
}


# --------------------------------------------------------------------------- #
# Package compilation
# --------------------------------------------------------------------------- #


def compile_mission(body: list[MissionStep], *, takeoff_alt_m: float = 18.0) -> list[MissionStep]:
    """Wrap shot steps into a legal mission shape: takeoff first,
    return_home + land last (SEQ-01's required frame)."""
    return [
        Takeoff(action="takeoff", alt_m=takeoff_alt_m),
        *body,
        ReturnHome(action="return_home"),
        Land(action="land"),
    ]


def exterior_package(prop: Property) -> list[MissionStep]:
    """Shot library v1's flagship: the full exterior listing package.

    front 3/4 hero -> 360 orbit with 8 bracketed captures -> rear elevated ->
    straight-down lot shot -> home. 11 captures, ~13 steps, comfortably inside
    the default Limits envelope and battery budget on the standard property.
    """
    body: list[MissionStep] = [
        *front_elevated_34(prop),
        *exterior_orbit(prop),
        *rear_elevated(prop),
        *lot_overhead(prop),
    ]
    return compile_mission(body, takeoff_alt_m=18.0)
