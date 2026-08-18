"""D12 hardening regression tests — one per CONFIRMED defect from the
2026-08-16 external review (chatgpt_code_review_081626.md), written to FAIL on
the pre-D12 code and pin the fixes forever.

The doctrine changes they encode (operator decisions, 2026-08-17):
- KILL SWITCH = FREEZE ONLY. An open breaker stops every command immediately
  (mid-orbit, mid-retry, mid-recovery). The single exempt command is
  abort_motion (freeze in place); the software then STANDS DOWN — no RTL, no
  land through an open breaker. Onboard failsafes / the operator own the
  aircraft from there.
- PREEMPT FIRST, AUDIT AFTER. abort()/kill() take effect before any SQLite
  write; a dying audit log can never eat a safety action.
- UNKNOWN IS AIRBORNE. Missing/stale telemetry is never evidence of safety:
  fail-closed snapshots (PX4), freshness-checked touchdown evidence, and
  recovery that ATTEMPTS the flight home when state is unknown.
- NOTHING ESCAPES WITHOUT A TERMINAL STATE. Untyped exceptions cross one
  boundary that records, recovers best-effort, and returns FAILED.
- APPROVAL BINDS TO PROOF. A validation report carries the plan hash + the
  rule manifest it ran; approval refuses reports that don't prove THIS plan
  passed the required set. The dashboard approves a specific reviewed
  mission_id+hash, not "whatever is pending".
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from types import SimpleNamespace

import pytest

from backends.px4_mavsdk import PX4Backend, PX4Config
from core.approval import ApprovalError, grant_approval
from core.engine import ExecutorTuning, MissionOutcome
from core.interfaces import CommandRejected, CommandTimeout
from core.policy.engine import validate_plan
from core.policy.rules_wave4 import CAPTURE_DWELL_S, ValidationContext
from core.policy.types import ValidationReport
from core.schema import CaptureSpec, GeoPoint, MissionPlan
from tests.conftest import good_plan_dict
from tests.test_executor import build

TERMINAL_STATES = {"completed", "failed", "rejected", "manually_overridden"}


async def _wait_for_dispatch(log, mission_id: str, action: str, tries: int = 400) -> None:
    for _ in range(tries):
        await asyncio.sleep(0.005)
        if any(
            e.type == "step.dispatched" and e.payload.get("action") == action
            for e in log.replay(mission_id)
        ):
            return
    raise AssertionError(f"never saw step.dispatched for {action}")


# --------------------------------------------------------------------------- #
# C1 — the kill switch can no longer be outrun
# --------------------------------------------------------------------------- #


async def test_breaker_trip_mid_orbit_stops_commands_immediately(good_plan):
    """Review probe: tripped mid-orbit, counted 41 commands afterward. The fix:
    every backend command re-checks the breaker immediately before dispatch —
    an open breaker mid-orbit means the REST OF THE ORBIT never flies."""
    mk, backend, log, clock = build(good_plan)
    ex = await mk()

    state = {"cut": None}
    orig_capture = backend.capture_photo

    async def capturing(spec, *, idem):
        ref = await orig_capture(spec, idem=idem)
        if state["cut"] is None:
            ex.breaker.trip("range safety: KILL")   # latch only — no kill() call:
            state["cut"] = len(backend.command_log)  # the guard alone must stop us
        return ref

    backend.capture_photo = capturing
    result = await asyncio.wait_for(ex.run(), timeout=5.0)

    after = [a for a, _ in backend.command_log[state["cut"]:]]
    assert "goto" not in after, f"orbit kept flying after the trip: {after}"
    assert "capture_photo" not in after
    assert "return_home" not in after and "land" not in after  # freeze-only doctrine
    assert result.outcome == MissionOutcome.FAILED
    assert "breaker" in result.reason.lower()
    assert backend.abort_motion_calls >= 1          # the one exempt command


async def test_recovery_through_open_breaker_freezes_only(good_plan):
    """Review: recovery sent RTL+land straight through an open breaker. Now an
    abort with the breaker open freezes and stands down — honestly FAILED."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_for_dispatch(log, good_plan.mission_id, "goto")

    ex.breaker.trip("operator kill switch")
    cut = len(backend.command_log)
    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)

    after = [a for a, _ in backend.command_log[cut:]]
    assert "return_home" not in after and "land" not in after
    assert backend.abort_motion_calls >= 1
    assert result.outcome == MissionOutcome.FAILED
    assert ex.machine.current_state.id in TERMINAL_STATES


async def test_kill_preempts_hung_step(good_plan):
    """kill() is the breaker's preemptive arm: trip + cancel the in-flight
    command NOW — a hung goto cannot delay the kill switch."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_for_dispatch(log, good_plan.mission_id, "goto")

    cut = len(backend.command_log)
    ex.kill(reason="operator kill switch", operator="mike")
    result = await asyncio.wait_for(task, timeout=2.0)   # returns promptly

    assert ex.breaker.is_open                            # kill also latches
    after = [a for a, _ in backend.command_log[cut:]]
    assert "return_home" not in after and "land" not in after
    assert result.outcome == MissionOutcome.FAILED
    assert "breaker" in result.reason.lower() or "kill" in result.reason.lower()


# --------------------------------------------------------------------------- #
# C2 — abort is preemptive and recovery is state-aware, bounded, log-proof
# --------------------------------------------------------------------------- #


async def test_abort_during_return_home_reaches_terminal_state(good_plan):
    """Review repro: abort during planned RTL raised TransitionNotAllowed
    (returning -> returning) and the mission ended with NO terminal state."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("return_home", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_for_dispatch(log, good_plan.mission_id, "return_home")

    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)   # must NOT raise

    assert result.outcome == MissionOutcome.ABORTED
    assert ex.machine.current_state.id in TERMINAL_STATES
    assert backend.in_air is False                        # recovery still landed it


async def test_abort_during_land_reaches_terminal_state(good_plan):
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("land", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_for_dispatch(log, good_plan.mission_id, "land")

    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)

    assert result.outcome == MissionOutcome.ABORTED
    assert ex.machine.current_state.id in TERMINAL_STATES
    assert backend.in_air is False


async def test_abort_survives_audit_log_failure(good_plan):
    """Review probe: a SQLite error during abort() ate the abort (event never
    set, task never cancelled). Preempt first; the audit write is best-effort.
    (Mike's iCloud disk has ACTUALLY thrown 'disk I/O error' — this is real.)"""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_for_dispatch(log, good_plan.mission_id, "goto")

    def dying_record(*a, **k):
        raise sqlite3.OperationalError("disk I/O error")

    ex.rec.record = dying_record
    ex.abort()                                            # must not raise
    result = await asyncio.wait_for(task, timeout=5.0)    # must still terminate

    assert result.outcome in (MissionOutcome.ABORTED, MissionOutcome.FAILED)
    assert ex.machine.current_state.id in TERMINAL_STATES
    assert backend.in_air is False                        # recovery still flew


async def test_hung_recovery_is_bounded(good_plan):
    """Review probe: a hung recovery RTL left the aircraft airborne in
    'returning' forever. Recovery commands now run under their own watchdog."""
    mk, backend, log, clock = build(
        good_plan,
        tuning=ExecutorTuning(
            timeout_factor=2.0, timeout_floor_s=0.25, recovery_cmd_timeout_s=0.3
        ),
    )
    backend.hooks[("goto", 0)] = "hang"
    backend.hooks[("return_home", 0)] = "hang"            # recovery RTL hangs too
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_for_dispatch(log, good_plan.mission_id, "goto")

    ex.abort()
    result = await asyncio.wait_for(task, timeout=4.0)    # bounded, not forever

    assert result.outcome == MissionOutcome.FAILED
    assert "unresolved" in result.reason
    assert ex.machine.current_state.id in TERMINAL_STATES


async def test_recovery_attempts_flight_when_telemetry_unknown(good_plan):
    """Review: recovery read `not tel.in_air` (or tel=None) as 'on the ground,
    skip recovery'. Unknown is AIRBORNE: with no telemetry, recovery must still
    attempt the flight home — and the outcome stays honestly unresolved."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_for_dispatch(log, good_plan.mission_id, "goto")

    async def no_telemetry():
        return None

    backend.latest_telemetry = no_telemetry
    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)

    actions = [a for a, _ in backend.command_log]
    assert "return_home" in actions, "recovery must be ATTEMPTED when state is unknown"
    assert result.outcome == MissionOutcome.FAILED        # no touchdown EVIDENCE
    assert "unresolved" in result.reason


async def test_landed_evidence_requires_fresh_telemetry(good_plan):
    """A stale on-ground snapshot must never prove touchdown."""
    mk, backend, log, clock = build(good_plan)
    ex = await mk()
    backend.in_air = False
    backend.telemetry_lag_s = 999.0                       # ancient data
    assert await ex._landed_evidence() is False


# --------------------------------------------------------------------------- #
# C7 — untyped failures cross ONE boundary into a terminal state
# --------------------------------------------------------------------------- #


async def test_untyped_backend_error_reaches_terminal_state(good_plan):
    """Review probe: a RuntimeError escaped everything — state 'executing',
    airborne, no terminal result. Now: recorded, recovered, FAILED."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("capture_photo", 0)] = RuntimeError("filesystem exploded")
    ex = await mk()

    result = await asyncio.wait_for(ex.run(), timeout=5.0)   # must NOT raise

    assert result.outcome == MissionOutcome.FAILED
    assert "RuntimeError" in result.reason
    assert ex.machine.current_state.id in TERMINAL_STATES
    actions = [a for a, _ in backend.command_log]
    assert "return_home" in actions                       # best-effort recovery flew
    types = [e.type for e in log.replay(good_plan.mission_id)]
    assert "error.untyped" in types


# --------------------------------------------------------------------------- #
# C3 — approval binds to PROOF that this plan passed the required rules
# --------------------------------------------------------------------------- #


async def _alive_ctx() -> ValidationContext:
    from backends.fake import FakeBackend

    backend = FakeBackend(clock=time.time)
    tel = await backend.latest_telemetry()
    return ValidationContext(
        now_ts=time.time(), telemetry=tel, capabilities=backend.capabilities()
    )


async def test_forged_empty_report_cannot_approve(good_plan):
    """Review probe: ValidationReport(results=[]) is vacuously ok and approved
    a speed-violating plan. An empty report proves nothing — refuse it."""
    forged = ValidationReport(results=[], live_checked=True)
    with pytest.raises(ApprovalError):
        grant_approval(good_plan, forged, operator="mike", now_ts=time.time())


async def test_report_from_different_plan_cannot_approve(good_plan):
    other = MissionPlan.model_validate(
        {**good_plan_dict(), "mission_id": "01OTHERMISSION000000000000"}
    )
    ctx = await _alive_ctx()
    report_for_other = validate_plan(other, ctx)
    with pytest.raises(ApprovalError):
        grant_approval(good_plan, report_for_other, operator="mike", now_ts=time.time())


async def test_engine_report_still_approves(good_plan):
    ctx = await _alive_ctx()
    report = validate_plan(good_plan, ctx)
    approval = grant_approval(good_plan, report, operator="mike", now_ts=time.time())
    assert approval.plan_hash


# --------------------------------------------------------------------------- #
# C4/C6/C8 — PX4 adapter: fail-closed telemetry, enforced speed, honest
# idempotency, honest brackets
# --------------------------------------------------------------------------- #

_NOW = time.time
_POS = SimpleNamespace(latitude_deg=36.1536, longitude_deg=-95.9932, relative_altitude_m=12.0)
_VEL0 = SimpleNamespace(north_m_s=0.0, east_m_s=0.0, down_m_s=0.0)


def _px4(**cfg) -> PX4Backend:
    return PX4Backend(clock=time.time, config=PX4Config(**cfg))


def _prime(b: PX4Backend, *, vel=_VEL0, skip: str | None = None) -> None:
    now = time.time()
    for key, val in (
        ("position", _POS), ("velocity", vel), ("in_air", True), ("armed", True),
    ):
        if key != skip:
            b._cache[key] = (val, now)


async def test_missing_critical_stream_fails_closed():
    """Review probe: fresh position + missing in_air still produced a snapshot
    with synthesized in_air=False. A missing critical stream = NO snapshot."""
    b = _px4()
    _prime(b, skip="in_air")
    assert await b.latest_telemetry() is None


async def test_all_critical_streams_present_returns_snapshot():
    b = _px4()
    _prime(b)
    tel = await b.latest_telemetry()
    assert tel is not None and tel.in_air is True


async def test_goto_overspeed_after_rejected_speed_command_is_typed_failure():
    """Review probe: set_current_speed failure swallowed, goto sent anyway,
    success reported at firmware cruise. If the approved speed can't be
    established AND the vehicle is observed exceeding it, that is a typed
    failure the executor must see — never silent success."""
    b = _px4(command_wait_s=1.0)
    _prime(b, vel=SimpleNamespace(north_m_s=9.0, east_m_s=0.0, down_m_s=0.0))
    b._home_abs_alt = 100.0

    async def set_speed(v):
        raise RuntimeError("DENIED: not in offboard")

    sent = []

    async def goto_location(*a):
        sent.append(a)

    b._system = SimpleNamespace(
        action=SimpleNamespace(set_current_speed=set_speed, goto_location=goto_location)
    )
    with pytest.raises(CommandRejected):
        await b.goto(GeoPoint(lat=36.16, lon=-95.99), 20.0, 4.0, None, idem="d12:spd")


async def test_ambiguous_goto_retry_does_not_resend_command():
    """Review probe: accepted-but-unconfirmed goto was re-SENT on retry with
    the same key. The in-flight registry reconciles instead: re-await the
    evidence, do not re-command the vehicle."""
    b = _px4(command_wait_s=0.15)
    _prime(b)                                   # never reaches the target
    b._home_abs_alt = 100.0
    sent = []

    async def set_speed(v):
        return None

    async def goto_location(*a):
        sent.append(a)

    b._system = SimpleNamespace(
        action=SimpleNamespace(set_current_speed=set_speed, goto_location=goto_location)
    )
    target = GeoPoint(lat=36.16, lon=-95.99)
    with pytest.raises(CommandTimeout):
        await b.goto(target, 20.0, 4.0, None, idem="d12:idem")
    assert len(sent) == 1
    with pytest.raises(CommandTimeout):        # executor retry, SAME key
        await b.goto(target, 20.0, 4.0, None, idem="d12:idem")
    assert len(sent) == 1, "ambiguous retry must reconcile, not re-send"


async def test_bracket3_capture_writes_three_frames(tmp_path):
    """Review: capabilities advertised bracket3/5 but capture wrote ONE jpeg
    regardless. Honest brackets: bracketN writes N frames, sidecar lists them."""
    b = _px4(media_dir=str(tmp_path / "media"))
    _prime(b)
    ref = await b.capture_photo(CaptureSpec(mode="bracket3", tag="d12"), idem="d12:b3")
    jpgs = sorted((tmp_path / "media").glob("*.jpg"))
    assert len(jpgs) == 3, f"bracket3 must produce 3 frames, got {[p.name for p in jpgs]}"
    import json as _json

    sidecar = _json.loads((tmp_path / "media" / f"{ref.media_id}_d12.json").read_text())
    assert len(sidecar["frames"]) == 3


# --------------------------------------------------------------------------- #
# Orbit executes EXACTLY the forecast — including dense cadence (review catch)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("arc", "every"),
    [(360.0, 10.0), (100.0, 30.0), (90.0, 45.0)],
)
async def test_orbit_dense_cadence_execution_matches_forecast(arc, every):
    """Review probe: 360°/10° flew 32 photos vs 37 forecast (12° segments,
    max one capture per waypoint). Capture angles are now first-class
    waypoints: execution == orbit_capture_count() at EVERY legal cadence."""
    d = good_plan_dict()
    for s in d["steps"]:
        if s["action"] == "orbit":
            s["arc_deg"], s["captures_every_deg"] = arc, every
    plan = MissionPlan.model_validate(d)
    expected = plan.expected_capture_count()

    mk, backend, log, clock = build(plan)
    ex = await mk()
    result = await asyncio.wait_for(ex.run(), timeout=10.0)

    assert result.outcome == MissionOutcome.COMPLETED
    assert len(result.media) == expected, (
        f"orbit {arc}/{every}: flew {len(result.media)} captures, forecast {expected}"
    )


def test_wave4_endurance_uses_shared_orbit_capture_count():
    """Review: PWR-02's dwell used int(arc//every) while execution uses
    orbit_capture_count() — a 100°/30° orbit under-budgeted one capture."""
    from core.policy.rules_wave4 import estimate_mission_duration_s
    from core.schema import orbit_capture_count

    def plan_with_orbit(capturing: bool) -> MissionPlan:
        d = good_plan_dict()
        for s in d["steps"]:
            if s["action"] == "orbit":
                s["arc_deg"] = 100.0
                if capturing:
                    s["captures_every_deg"] = 30.0
                else:
                    s.pop("captures_every_deg", None)
                    s.pop("capture", None)
        return MissionPlan.model_validate(d)

    dwell = (
        estimate_mission_duration_s(plan_with_orbit(True))
        - estimate_mission_duration_s(plan_with_orbit(False))
    )
    n = round(dwell / CAPTURE_DWELL_S)
    assert n == orbit_capture_count(100.0, 30.0), (
        f"endurance budgets {n} orbit captures; execution will fly "
        f"{orbit_capture_count(100.0, 30.0)}"
    )
