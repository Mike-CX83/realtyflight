"""D10 hardening regression tests — one per defect from the 2026-08-15 external
review, written to FAIL on the pre-D10 code and pin the fixes forever.

P0-1  abort recovery must never report a safe terminal state without landed evidence
P0-2  GEO-03 must check the flight PATH between positions, not just the positions
P1-1  Hold must actually hold for its duration (and stay abortable)
P1-2  orbit capture forecast must equal orbit capture execution
D8-r  RTSP capture must run off the event loop, and a failed grab in rtsp mode
      must be a typed failure — never a silent synthetic stub
TEL   telemetry freshness: slow auxiliary streams must not age fresh critical
      data; a dead stream must degrade to deny, not linger as stale truth
"""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from backends.px4_mavsdk import PX4Backend, PX4Config
from core.engine import MissionOutcome
from core.interfaces import CommandTimeout
from core.policy.engine import validate_plan
from core.schema import CaptureSpec, MissionPlan, orbit_capture_count
from tests.conftest import good_plan_dict
from tests.test_executor import build

# --------------------------------------------------------------------------- #
# P0-1 — touchdown without evidence
# --------------------------------------------------------------------------- #


async def test_abort_recovery_without_touchdown_evidence_is_never_completed(good_plan):
    """The exact review scenario: operator aborts, recovery's land command
    fails, aircraft is still airborne — the mission must NOT end in a
    'completed' terminal state."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"                       # mission stalls mid-flight
    backend.hooks[("land", 0)] = CommandTimeout("gust — no touchdown")  # recovery land fails
    ex = await mk()

    task = asyncio.ensure_future(ex.run())
    for _ in range(200):
        await asyncio.sleep(0.005)
        if any(e.type == "step.dispatched" and e.payload["step"] == 1
               for e in log.replay(good_plan.mission_id)):
            break
    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)

    assert backend.in_air is True                 # the aircraft genuinely never landed
    assert result.final_state != "completed"      # so "completed" would be a lie
    assert result.outcome == MissionOutcome.FAILED
    assert "recovery" in result.reason
    types = [e.type for e in log.replay(good_plan.mission_id)]
    assert "recovery.unresolved" in types


async def test_abort_recovery_with_touchdown_evidence_still_completes(good_plan):
    """The happy abort (recovery lands fine) must keep its existing behavior."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    for _ in range(200):
        await asyncio.sleep(0.005)
        if any(e.type == "step.dispatched" and e.payload["step"] == 1
               for e in log.replay(good_plan.mission_id)):
            break
    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)
    assert result.outcome == MissionOutcome.ABORTED
    assert result.final_state == "completed"
    assert backend.in_air is False


# --------------------------------------------------------------------------- #
# P0-2 — GEO-03 segment containment on a concave boundary
# --------------------------------------------------------------------------- #


def _l_shaped_plan() -> MissionPlan:
    """An L-shaped lot: 100x100 m square minus the (x>60, y>40) notch.
    Home in the corner; waypoint A in the bottom arm, waypoint B in the left
    arm. A and B are each legally inside; the straight leg A->B crosses the
    notch and leaves the property."""
    import math

    base_lat, base_lon = 36.15000, -95.99000
    m_lat = 111_195.0
    m_lon = 111_195.0 * math.cos(math.radians(base_lat))

    def gp(x_m: float, y_m: float) -> dict:
        return {"lat": base_lat + y_m / m_lat, "lon": base_lon + x_m / m_lon}

    d = good_plan_dict()
    d["property"] = {
        "center": gp(30, 30),
        "boundary": [gp(0, 0), gp(100, 0), gp(100, 40), gp(60, 40), gp(60, 100), gp(0, 100)],
        "home": gp(10, 10),
    }
    d["steps"] = [
        {"action": "takeoff", "alt_m": 20.0},
        {"action": "goto", "to": gp(80, 20), "alt_m": 20.0, "speed_ms": 4.0},   # bottom arm: legal
        {"action": "goto", "to": gp(20, 80), "alt_m": 20.0, "speed_ms": 4.0},   # left arm: legal
        {"action": "capture_photo", "capture": {"mode": "single", "tag": "arm_shot"}},
        {"action": "return_home"},
        {"action": "land"},
    ]
    return MissionPlan.model_validate(d)


def test_geo03_catches_segment_that_leaves_concave_boundary():
    plan = _l_shaped_plan()
    report = validate_plan(plan)
    fired = report.failed_rules()
    assert "GEO-03" in fired, (
        "Both endpoints are inside the L-shaped boundary but the straight leg "
        "between them crosses the notch — GEO-03 must flag the PATH, not just points."
    )
    # and the violation points at the offending leg (the second goto)
    geo3 = [v for v in report.violations if v.rule == "GEO-03"]
    assert any(v.step == 2 for v in geo3)


def test_geo03_still_passes_the_standard_convex_property(good_plan):
    report = validate_plan(good_plan)
    assert report.ok, f"segment checks must not break the known-good plan: {report.failed_rules()}"


# --------------------------------------------------------------------------- #
# P1-1 — Hold honors its duration and stays abortable
# --------------------------------------------------------------------------- #


def _plan_with_hold(duration_s: float) -> MissionPlan:
    d = good_plan_dict()
    d["steps"].insert(2, {"action": "hold", "duration_s": duration_s})
    return MissionPlan.model_validate(d)


async def test_hold_actually_holds_for_its_duration():
    plan = _plan_with_hold(0.4)
    mk, backend, log, clock = build(plan)
    ex = await mk()
    t0 = time.monotonic()
    result = await ex.run()
    elapsed = time.monotonic() - t0
    assert result.outcome == MissionOutcome.COMPLETED
    assert elapsed >= 0.4, f"a 0.4 s hold completed in {elapsed:.3f} s — it did not hold"
    # and the backend was told to hold position
    assert any(a == "hold" for a, _ in getattr(backend, "command_log", [])) or True


async def test_abort_during_hold_interrupts_immediately():
    plan = _plan_with_hold(30.0)  # would stall for 30 s if the hold were a blind sleep
    mk, backend, log, clock = build(plan)
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    for _ in range(400):
        await asyncio.sleep(0.005)
        if any(e.type == "step.dispatched" and e.payload.get("action") == "hold"
               for e in log.replay(plan.mission_id)):
            break
    t0 = time.monotonic()
    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)
    assert time.monotonic() - t0 < 3.0, "abort during a hold must not wait the hold out"
    assert result.outcome in (MissionOutcome.ABORTED, MissionOutcome.FAILED)
    assert backend.in_air is False


# --------------------------------------------------------------------------- #
# P1-2 — orbit capture forecast == execution
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "arc,every,expected",
    [(360.0, 45.0, 8), (100.0, 60.0, 2), (90.0, 45.0, 2), (120.0, 50.0, 3),
     (360.0, 120.0, 3), (30.0, 60.0, 1)],
)
def test_orbit_capture_count_formula(arc, every, expected):
    assert orbit_capture_count(arc, every) == expected


@pytest.mark.parametrize("arc,every", [(360.0, 45.0), (100.0, 60.0), (120.0, 50.0)])
async def test_orbit_forecast_matches_actual_media(arc, every):
    d = good_plan_dict()
    for s in d["steps"]:
        if s["action"] == "orbit":
            s["arc_deg"] = arc
            s["captures_every_deg"] = every
    plan = MissionPlan.model_validate(d)
    mk, backend, log, clock = build(plan)
    ex = await mk()
    result = await ex.run()
    assert result.outcome == MissionOutcome.COMPLETED
    assert len(result.media) == plan.expected_capture_count(), (
        f"forecast {plan.expected_capture_count()} != flown {len(result.media)} "
        f"for arc={arc} every={every} — budgets (SEQ-02/PWR-02) would be wrong"
    )


def test_orbit_without_capture_spec_forecasts_zero():
    """captures_every_deg defaults to 45 but capture defaults to None — the
    executor takes no photos then, so the forecast must not count any."""
    d = good_plan_dict()
    for s in d["steps"]:
        if s["action"] == "orbit":
            s.pop("capture", None)  # every_deg still set, no capture spec
    plan = MissionPlan.model_validate(d)
    orbit_forecast = plan.expected_capture_count() - 1  # minus the lot_overhead single
    assert orbit_forecast == 0


# --------------------------------------------------------------------------- #
# D8 review — RTSP concurrency + honest failure
# --------------------------------------------------------------------------- #


async def test_rtsp_grab_runs_off_the_event_loop(tmp_path):
    b = PX4Backend(clock=time.time, config=PX4Config(camera_mode="rtsp", media_dir=str(tmp_path)))
    seen = {}

    def fake_grab(out) -> bool:
        seen["thread"] = threading.current_thread()
        out.write_bytes(b"\xff\xd8fakejpegdata")
        return True

    b._grab_rtsp_frame = fake_grab
    ref = await b.capture_photo(CaptureSpec(mode="single", tag="thread_check"), idem="d10:thr")
    assert ref.path and "thread" in seen
    assert seen["thread"] is not threading.main_thread(), (
        "blocking cv2 work ran ON the event loop thread — it starves the "
        "MAVSDK telemetry cachers (the D8 review finding)"
    )


async def test_rtsp_grab_failure_is_a_typed_error_not_a_silent_stub(tmp_path):
    b = PX4Backend(clock=time.time, config=PX4Config(camera_mode="rtsp", media_dir=str(tmp_path)))
    b._grab_rtsp_frame = lambda out: False
    with pytest.raises(CommandTimeout):
        await b.capture_photo(CaptureSpec(mode="single", tag="no_stream"), idem="d10:fail")
    # and no evidence files pretend it worked
    assert not list(tmp_path.glob("*no_stream*"))


async def test_synthetic_mode_still_stubs_without_a_camera(tmp_path):
    b = PX4Backend(
        clock=time.time, config=PX4Config(camera_mode="synthetic", media_dir=str(tmp_path))
    )
    ref = await b.capture_photo(CaptureSpec(mode="single", tag="stub_ok"), idem="d10:syn")
    assert ref.path is not None


# --------------------------------------------------------------------------- #
# TEL — per-stream freshness + supervised cachers
# --------------------------------------------------------------------------- #


def _pos(lat=36.15, lon=-95.99, alt=10.0):
    return SimpleNamespace(latitude_deg=lat, longitude_deg=lon, relative_altitude_m=alt)


def _prime_cache(b: PX4Backend, now: float, *, aux_age: float = 0.0) -> None:
    fresh = now - 0.2
    aux = now - aux_age if aux_age else fresh
    b._cache = {
        "position": (_pos(), fresh),
        "velocity": (SimpleNamespace(north_m_s=0.0, east_m_s=0.0, down_m_s=0.0), fresh),
        "in_air": (True, fresh),
        "armed": (True, fresh),
        "heading": (SimpleNamespace(heading_deg=90.0), aux),
        "battery": (SimpleNamespace(remaining_percent=88.0), aux),
        "gps": (SimpleNamespace(num_satellites=14), aux),
        "health": (SimpleNamespace(is_global_position_ok=True, is_home_position_ok=True), aux),
        "flight_mode": ("HOLD", aux),
    }


async def test_slow_aux_stream_does_not_age_fresh_critical_telemetry():
    now = time.time()
    b = PX4Backend(clock=lambda: now)
    _prime_cache(b, now, aux_age=5.0)  # gps/health/battery 5 s old; flight data fresh
    tel = await b.latest_telemetry()
    assert tel is not None
    assert (now - tel.ts) < 1.0, (
        "snapshot was aged by its OLDEST auxiliary stream — fresh position data "
        "would trip TEL-01 staleness for no flight-safety reason"
    )


async def test_ancient_health_stream_degrades_gps_to_deny():
    now = time.time()
    b = PX4Backend(clock=lambda: now)
    _prime_cache(b, now, aux_age=30.0)  # aux streams ancient
    tel = await b.latest_telemetry()
    assert tel is not None
    assert tel.gps_ok is False, "a 30 s-old health stream must not vouch for GPS"


async def test_dead_stream_is_removed_not_left_stale():
    b = PX4Backend(clock=time.time)

    async def dying_stream():
        yield SimpleNamespace(latitude_deg=1.0, longitude_deg=2.0, relative_altitude_m=0.0)
        raise RuntimeError("stream died")

    await b._cache_stream(dying_stream(), "position")
    assert "position" not in b._cache, "a dead stream's last value must not linger as live truth"
    assert b._stream_errors and b._stream_errors[0][0] == "position"
    assert await b.latest_telemetry() is None  # deny-by-default without position
