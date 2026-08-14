"""MissionPlan schema v1 — the ONLY vocabulary the LLM may emit.

Design rules (docs/architecture-research/08 §3):
- Every model forbids unknown fields (extra="forbid"): an invented action or extra
  key is a parse failure, not a warning.
- Every quantity is unit-suffixed (_m, _ms for m/s, _deg, _s, _pct).
- Steps are a discriminated union on `action`; new capability = new typed step
  + new policy rules + new tests. Never a free-form dict.
- The schema enforces per-field sanity (ranges/types). Contextual safety
  (geofence, battery, sequences) lives in core/policy — deliberately separate,
  so the safety story never depends on the parser alone.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Shared primitives
# --------------------------------------------------------------------------- #


class _Model(BaseModel):
    """Base: unknown fields are rejected everywhere."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeoPoint(_Model):
    """WGS84 coordinate."""

    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class Property(_Model):
    """The operator-confirmed property definition (drawn on the satellite map)."""

    center: GeoPoint
    boundary: list[GeoPoint] = Field(min_length=3, max_length=64)
    home: GeoPoint  # launch / RTH point; must lie inside boundary (GEO-02)


class Limits(_Model):
    """Numeric envelope for this mission. Schema caps are absolute; policy may
    tighten further, never loosen."""

    max_alt_m: float = Field(default=40.0, gt=0.0, le=120.0)  # 120 m ~ Part 107 400 ft
    max_speed_ms: float = Field(default=5.0, gt=0.0, le=8.0)  # 8 m/s = ANAFI OA envelope
    max_home_dist_m: float = Field(default=150.0, gt=0.0, le=500.0)
    max_steps: int = Field(default=40, ge=1, le=60)
    max_captures: int = Field(default=40, ge=1, le=60)
    acceptance_radius_m: float = Field(default=2.5, ge=0.5, le=10.0)  # "arrived" tolerance
    min_takeoff_alt_m: float = Field(default=5.0, ge=2.0, le=20.0)
    min_orbit_alt_m: float = Field(default=8.0, ge=3.0, le=30.0)


class FailsafePolicy(_Model):
    """Deterministic responses. Enums grow only with evidence (doc 01 S10)."""

    on_gps_loss: Literal["hold_then_rth"] = "hold_then_rth"
    gps_hold_timeout_s: float = Field(default=10.0, ge=2.0, le=60.0)
    on_link_loss: Literal["backend_native_rth"] = "backend_native_rth"
    on_low_battery: Literal["rth"] = "rth"
    battery_floor_pct: float = Field(default=30.0, ge=15.0, le=60.0)
    battery_reserve_pct: float = Field(default=20.0, ge=10.0, le=50.0)
    telemetry_stale_hold_s: float = Field(default=2.0, ge=0.5, le=10.0)
    telemetry_stale_failsafe_s: float = Field(default=10.0, ge=2.0, le=60.0)


class CaptureSpec(_Model):
    """What to capture. bracket3/bracket5 map 1:1 to ANAFI camera2 bracketing;
    the PX4 sim backend emulates them as evidence frames."""

    mode: Literal["single", "bracket3", "bracket5"] = "bracket3"
    tag: str = Field(pattern=r"^[a-z0-9_]{1,40}$")  # e.g. "front_34_elevated"


# --------------------------------------------------------------------------- #
# Mission steps — the closed action vocabulary
# --------------------------------------------------------------------------- #


class Takeoff(_Model):
    action: Literal["takeoff"]
    alt_m: float = Field(gt=0.0, le=120.0)


class Goto(_Model):
    action: Literal["goto"]
    to: GeoPoint
    alt_m: float = Field(gt=0.0, le=120.0)
    speed_ms: float = Field(default=5.0, gt=0.0, le=8.0)


class Orbit(_Model):
    action: Literal["orbit"]
    center: GeoPoint
    radius_m: float = Field(ge=8.0, le=100.0)
    alt_m: float = Field(gt=0.0, le=120.0)
    speed_ms: float = Field(default=3.0, gt=0.0, le=5.0)
    arc_deg: float = Field(default=360.0, gt=0.0, le=360.0)
    direction: Literal["cw", "ccw"] = "cw"
    captures_every_deg: float | None = Field(default=45.0, ge=10.0, le=180.0)
    capture: CaptureSpec | None = None
    yaw_mode: Literal["face_center"] = "face_center"


class SetGimbal(_Model):
    action: Literal["set_gimbal"]
    pitch_deg: float = Field(ge=-90.0, le=10.0)


class CapturePhoto(_Model):
    action: Literal["capture_photo"]
    capture: CaptureSpec


class Hold(_Model):
    action: Literal["hold"]
    duration_s: float = Field(gt=0.0, le=60.0)


class ReturnHome(_Model):
    action: Literal["return_home"]


class Land(_Model):
    action: Literal["land"]


MissionStep = Annotated[
    Union[Takeoff, Goto, Orbit, SetGimbal, CapturePhoto, Hold, ReturnHome, Land],
    Field(discriminator="action"),
]

FLYING_ACTIONS: frozenset[str] = frozenset({"goto", "orbit"})
WORK_ACTIONS: frozenset[str] = frozenset(
    {"goto", "orbit", "set_gimbal", "capture_photo", "hold"}
)


# --------------------------------------------------------------------------- #
# The plan envelope
# --------------------------------------------------------------------------- #


class MissionPlan(_Model):
    plan_version: Literal[1]
    mission_id: str = Field(min_length=1, max_length=64)
    request_text: str = Field(min_length=1, max_length=2000)
    summary: str = Field(min_length=1, max_length=2000)
    property: Property
    limits: Limits = Limits()
    failsafe: FailsafePolicy = FailsafePolicy()
    steps: list[MissionStep] = Field(min_length=1, max_length=60)

    # ---- derived helpers (not serialized) ---------------------------------- #

    def expected_capture_count(self) -> int:
        """Total photos this plan will attempt (CapturePhoto steps + orbit captures)."""
        count = 0
        for step in self.steps:
            if isinstance(step, CapturePhoto):
                count += 1
            elif isinstance(step, Orbit) and step.captures_every_deg is not None:
                count += max(1, int(step.arc_deg // step.captures_every_deg))
        return count


def compute_plan_hash(plan: MissionPlan) -> str:
    """Canonical hash an approval binds to (APR-01). Any change to any field
    changes the hash and voids prior approval."""
    canonical = json.dumps(
        plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
