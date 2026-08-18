"""Shot library v1 tests (D9) — geometry, validity, and a full library-compiled
mission flown on the fake backend. Also pins the Goto.yaw_deg schema addition
and its plumb-through to the backend."""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from backends.fake import FakeBackend
from core.approval import grant_approval
from core.engine import ExecutorTuning, MissionExecutor, MissionOutcome
from core.events import EventLog
from core.geo import distance_m
from core.policy import ValidationContext
from core.policy.engine import validate_plan
from core.schema import GeoPoint, Goto, MissionPlan, Property
from planner.shots import (
    aim_pitch_deg,
    bearing_deg,
    exterior_package,
    front_elevated_34,
    lot_overhead,
    offset,
)
from tests.conftest import good_plan_dict, good_telemetry_dict


def demo_property() -> Property:
    return Property.model_validate(good_plan_dict()["property"])


# ---------------------------------------------------------------------------- #
# Geometry
# ---------------------------------------------------------------------------- #


def test_offset_and_bearing_roundtrip():
    home = GeoPoint(lat=36.15360, lon=-95.99320)
    for brg, dist in [(0.0, 50.0), (90.0, 30.0), (215.0, 40.0)]:
        p = offset(home, brg, dist)
        assert abs(distance_m(home, p) - dist) < 0.5          # meters preserved
        assert abs((bearing_deg(home, p) - brg + 180) % 360 - 180) < 1.0  # bearing preserved


def test_front_34_position_is_on_the_home_side_facing_center():
    prop = demo_property()
    steps = front_elevated_34(prop)
    goto = steps[0]
    assert isinstance(goto, Goto)

    front = bearing_deg(prop.center, prop.home)
    actual = bearing_deg(prop.center, goto.to)
    diff = abs((actual - front + 180) % 360 - 180)
    assert diff == pytest.approx(35.0, abs=1.5)               # the 3/4 offset

    # the camera faces the structure: yaw looks from position back at center
    assert goto.yaw_deg == pytest.approx(bearing_deg(goto.to, prop.center), abs=0.1)
    # and the gimbal aims at it, in the elevated-shot band
    assert -45.0 <= steps[1].pitch_deg <= -15.0


def test_aim_pitch_is_sane_and_clamped():
    assert -35.0 < aim_pitch_deg(18.0, 25.0) < -25.0          # classic elevated
    assert -90.0 <= aim_pitch_deg(500.0, 1.0) < -89.0         # steep stays legal
    assert aim_pitch_deg(0.0, 5.0) == 10.0                    # below target: clamped ceiling
    assert aim_pitch_deg(0.0, 50.0) > -11.0                   # near-level, legal


def test_lot_overhead_is_straight_down_over_center():
    prop = demo_property()
    goto, gimbal, cap = lot_overhead(prop)
    assert distance_m(goto.to, prop.center) < 0.5
    assert gimbal.pitch_deg == -90.0
    assert cap.capture.tag == "lot_overhead"


# ---------------------------------------------------------------------------- #
# The compiled package is a valid, safe mission
# ---------------------------------------------------------------------------- #


def package_plan() -> MissionPlan:
    base = good_plan_dict()
    prop = demo_property()
    return MissionPlan(
        plan_version=1,
        mission_id=base["mission_id"],
        request_text="Full exterior package via the shot library.",
        summary="Library-compiled exterior package.",
        property=prop,
        steps=exterior_package(prop),
    )


def test_exterior_package_passes_every_static_rule():
    report = validate_plan(package_plan())
    assert report.ok, f"library output must be rule-clean: {report.failed_rules()}"


def test_exterior_package_capture_count_and_tags():
    plan = package_plan()
    assert plan.expected_capture_count() == 11  # front + 8 orbit + rear + overhead
    tags = [s.capture.tag for s in plan.steps
            if getattr(s, "capture", None) is not None]
    assert tags == ["front_34_elevated", "exterior_orbit", "rear_elevated", "lot_overhead"]


async def test_exterior_package_flies_on_fake_backend():
    from core.interfaces import TelemetrySnapshot

    plan = package_plan()
    clock = lambda: time.time()  # noqa: E731
    backend = FakeBackend(clock)
    log = EventLog(":memory:")
    live = ValidationContext(
        now_ts=time.time(),
        telemetry=TelemetrySnapshot.model_validate(
            good_telemetry_dict(ts=time.time() - 0.2)
        ),
        capabilities=backend.capabilities(),
    )
    report = validate_plan(plan, live)
    assert report.ok
    approval = grant_approval(plan, report, operator="mike", now_ts=time.time())
    ex = MissionExecutor(plan, approval, backend, log, clock=clock, profile="sim",
                         tuning=ExecutorTuning(timeout_factor=2.0, timeout_floor_s=0.25))
    result = await ex.run()

    assert result.outcome == MissionOutcome.COMPLETED
    assert len(result.media) == 11
    # yaw plumb: the fake's heading was steered by the LAST yawed goto —
    # the rear-elevated position, facing back at the center
    # (lot_overhead's goto has yaw None, so heading persists from the rear shot)
    yawed = [s for s in plan.steps if isinstance(s, Goto) and s.yaw_deg is not None]
    assert len(yawed) == 2  # front + rear
    assert backend.heading_deg == pytest.approx(yawed[-1].yaw_deg, abs=0.1)


# ---------------------------------------------------------------------------- #
# Goto.yaw_deg schema pin
# ---------------------------------------------------------------------------- #


def test_goto_yaw_schema_bounds():
    p = GeoPoint(lat=36.15, lon=-95.99)
    assert Goto(action="goto", to=p, alt_m=10.0).yaw_deg is None       # optional
    assert Goto(action="goto", to=p, alt_m=10.0, yaw_deg=359.9).yaw_deg == 359.9
    with pytest.raises(ValidationError):
        Goto(action="goto", to=p, alt_m=10.0, yaw_deg=360.0)           # exclusive top
    with pytest.raises(ValidationError):
        Goto(action="goto", to=p, alt_m=10.0, yaw_deg=-1.0)


def test_yaw_reaches_the_backend():
    """Executor must hand step.yaw_deg to backend.goto (was hardcoded None)."""
    import asyncio

    async def run() -> float:
        backend = FakeBackend(lambda: time.time())
        await backend.takeoff(10.0, idem="y:t")
        step = Goto(action="goto", to=GeoPoint(lat=36.154, lon=-95.9930),
                    alt_m=10.0, speed_ms=4.0, yaw_deg=123.0)
        await backend.goto(step.to, step.alt_m, step.speed_ms, step.yaw_deg, idem="y:g")
        return backend.heading_deg

    assert asyncio.run(run()) == pytest.approx(123.0)
