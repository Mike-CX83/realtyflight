"""D12.1 hardening regression tests — the 2026-08-17 review RERUN, absorbed.

The rerun verdict on D12 was 6/10 invariants verified, 4 broken (#5, #6, #8,
#10). Each test here pins one of the remaining confirmed defects, written to
FAIL on the D12 code:

- The per-command guard checked abort+breaker but not REALITY: battery/GPS/
  freshness/approval were only re-checked per top-level step (probe: battery
  to 0% mid-orbit -> 44 more commands). Now the FULL dispatch gate runs before
  every work command.
- A slow preflight could launder an expired approval (activated approvals
  never expire). The gate now re-runs after preflight, activation is atomic
  with the first cleared dispatch.
- Recovery commands ran outside the preemptible task slot: kill() during the
  recovery RTL let the LAND cross an open breaker. Recovery now shares the
  slot and rechecks the breaker before every command.
- hold() was only a flag; a kill while paused hung forever. hold() now
  PREEMPTS the in-flight step (resume re-dispatches on the same idem key —
  that is what idempotency is for) and the pause wait wakes on kill.
- Future-dated telemetry passed executor evidence checks (only positive age
  was bounded). Freshness is now 0 <= age <= limit, matching Wave-4.
- ABORTED missions could end with the state machine nonterminal (returning).
- mission.closed now records outcome + reason.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from backends.px4_mavsdk import PX4Backend, PX4Config
from core.engine import MissionOutcome
from core.interfaces import CommandRejected, CommandTimeout
from tests.test_executor import Clock, build

TERMINAL_STATES = {"completed", "failed", "rejected", "manually_overridden"}


async def _wait_event(log, mission_id: str, pred, tries: int = 600) -> None:
    for _ in range(tries):
        await asyncio.sleep(0.005)
        if any(pred(e) for e in log.replay(mission_id)):
            return
    raise AssertionError("expected event never appeared")


# --------------------------------------------------------------------------- #
# Rerun C1 — the FULL live gate runs before every command, not just the
# cheap abort/breaker guard
# --------------------------------------------------------------------------- #


async def test_battery_collapse_mid_orbit_stops_at_next_command(good_plan):
    """Rerun probe: battery to 0% after the first orbit waypoint -> 44 more
    goto/capture commands before the next top-level gate. Now the full gate
    (PWR/TEL/GPS/APR/ENV) runs before EVERY work command: the very next
    waypoint is refused and the failsafe flies it home."""
    mk, backend, log, clock = build(good_plan)
    ex = await mk()

    state = {"cut": None}
    orig_capture = backend.capture_photo

    async def capturing(spec, *, idem):
        ref = await orig_capture(spec, idem=idem)
        if state["cut"] is None:
            backend.battery_pct = 0.0                 # reality collapses
            state["cut"] = len(backend.command_log)
        return ref

    backend.capture_photo = capturing
    result = await asyncio.wait_for(ex.run(), timeout=5.0)

    after = [a for a, _ in backend.command_log[state["cut"]:]]
    assert after.count("goto") == 0, f"orbit kept flying on a dead battery: {after}"
    assert "capture_photo" not in after
    assert "return_home" in after                     # failsafe DID fly it home
    assert result.outcome == MissionOutcome.FAILED
    assert "PWR" in result.reason


# --------------------------------------------------------------------------- #
# Rerun C2 — a slow preflight cannot launder an expired approval
# --------------------------------------------------------------------------- #


async def test_expired_approval_cannot_activate_after_slow_preflight(good_plan):
    clock = Clock()
    mk, backend, log, _ = build(good_plan, clock=clock)
    ex = await mk()

    orig_preflight = backend.preflight

    async def slow_preflight():
        clock.t += 301.0                              # TTL is 300 s
        return await orig_preflight()

    backend.preflight = slow_preflight
    result = await asyncio.wait_for(ex.run(), timeout=5.0)

    assert result.outcome == MissionOutcome.REJECTED_AT_GATE
    assert "APR-01" in result.reason
    assert backend.command_log == []                  # nothing ever dispatched


# --------------------------------------------------------------------------- #
# Rerun C3 — kill preempts RECOVERY too; hold preempts; kill wakes paused
# --------------------------------------------------------------------------- #


async def test_kill_during_recovery_rtl_never_sends_land(good_plan):
    """Rerun probe: kill() during the recovery RTL — the RTL completed and
    LAND was sent through the open breaker. Recovery commands now live in the
    same preemptible slot and the breaker is rechecked before each."""
    from backends.fake import FakeConfig

    mk, backend, log, clock = build(good_plan, cfg=FakeConfig(time_scale=0.05))
    backend.hooks[("goto", 3)] = "hang"               # hang mid-orbit, far from home
    ex = await mk()
    task = asyncio.ensure_future(ex.run())

    for _ in range(800):                              # wait for the hung orbit leg
        await asyncio.sleep(0.005)
        if sum(1 for a, _ in backend.command_log if a == "goto") >= 4:
            break
    ex.abort()                                        # recovery starts (RTL is slow)
    await _wait_event(
        log, good_plan.mission_id,
        lambda e: e.type == "failsafe.dispatch" and e.payload.get("command") == "return_home",
    )
    cut = len(backend.command_log)
    ex.kill(reason="kill during recovery", operator="mike")
    result = await asyncio.wait_for(task, timeout=5.0)

    after = [a for a, _ in backend.command_log[cut:]]
    assert "land" not in after, "LAND crossed an open breaker during recovery"
    assert "return_home" not in after
    assert ex.breaker.is_open
    assert result.outcome == MissionOutcome.FAILED
    assert ex.machine.current_state.id in TERMINAL_STATES


async def test_hold_preempts_active_goto_and_resume_redispatches(good_plan):
    """Rerun: hold() was only a flag — the HTTP route said 'holding' while a
    hung goto kept the aircraft busy. hold() now cancels the in-flight step;
    resume re-dispatches the SAME step on the same idem key."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_event(
        log, good_plan.mission_id,
        lambda e: e.type == "step.dispatched" and e.payload.get("step") == 1,
    )

    ex.hold(operator="mike")
    for _ in range(400):                              # paused, promptly
        await asyncio.sleep(0.005)
        if ex.machine.current_state.id == "paused":
            break
    assert ex.machine.current_state.id == "paused", "hold did not preempt the hung goto"
    assert any(a == "hold" for a, _ in backend.command_log)

    ex.resume(operator="mike")
    result = await asyncio.wait_for(task, timeout=5.0)
    assert result.outcome == MissionOutcome.COMPLETED
    dispatches = [
        e for e in log.replay(good_plan.mission_id)
        if e.type == "step.dispatched" and e.payload["step"] == 1
    ]
    assert len(dispatches) == 2                       # original + post-resume re-dispatch


async def test_kill_while_paused_wakes_and_freezes(good_plan):
    """Rerun: _wait_resume() waited for resume|abort only — a kill while
    paused hung forever. It now wakes on kill and stands down (freeze)."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_event(
        log, good_plan.mission_id,
        lambda e: e.type == "step.dispatched" and e.payload.get("step") == 1,
    )
    ex.hold(operator="mike")
    for _ in range(400):
        await asyncio.sleep(0.005)
        if ex.machine.current_state.id == "paused":
            break
    # D12.2 tightening (independent-verification finding): the kill must be
    # tested FROM the paused state — without this assert, a broken hold would
    # let the test pass via the ordinary kill-from-executing path.
    assert ex.machine.current_state.id == "paused", "never reached paused"

    cut = len(backend.command_log)
    ex.kill(reason="kill while paused", operator="mike")
    result = await asyncio.wait_for(task, timeout=2.0)   # must NOT hang

    after = [a for a, _ in backend.command_log[cut:]]
    assert "return_home" not in after and "land" not in after  # freeze-only
    assert result.outcome == MissionOutcome.FAILED
    assert ex.machine.current_state.id in TERMINAL_STATES


# --------------------------------------------------------------------------- #
# Rerun C6 — future-dated telemetry is not evidence
# --------------------------------------------------------------------------- #


async def test_future_dated_telemetry_is_not_evidence(good_plan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()
    backend.in_air = False
    backend.telemetry_lag_s = -999.0                  # timestamp from the future
    assert await ex._landed_evidence() is False
    with pytest.raises(CommandTimeout):
        await ex._fresh_tel()


# --------------------------------------------------------------------------- #
# Rerun Important-3 — ABORTED never leaves the machine nonterminal
# --------------------------------------------------------------------------- #


async def test_abort_during_rtl_with_landed_evidence_settles_terminal(good_plan):
    """Rerun probe output: 'aborted returning returning' — landed evidence
    made recovery skip, but nothing drove returning -> terminal."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("return_home", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_event(
        log, good_plan.mission_id,
        lambda e: e.type == "step.dispatched" and e.payload.get("action") == "return_home",
    )
    # the sim landed itself while the RTL command hung (e.g., PX4 native RTL)
    backend.in_air = False
    backend.alt_rel_m = 0.0
    backend.vspeed_ms = 0.0
    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)

    assert result.outcome == MissionOutcome.ABORTED
    assert result.final_state == "completed"
    assert ex.machine.current_state.id in TERMINAL_STATES


# --------------------------------------------------------------------------- #
# Audit completeness — mission.closed carries the verdict
# --------------------------------------------------------------------------- #


async def test_mission_closed_records_outcome_and_reason(good_plan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()
    result = await ex.run()
    assert result.outcome == MissionOutcome.COMPLETED
    closed = [e for e in log.replay(good_plan.mission_id) if e.type == "mission.closed"]
    assert closed and closed[-1].payload.get("outcome") == "completed"
    # D12.2 tightening: reason is ALWAYS present (may be empty on success) —
    # a replay alone must carry the full verdict for every outcome.
    assert "reason" in closed[-1].payload


# --------------------------------------------------------------------------- #
# Rerun C4/C5 — PX4 adapter: gimbal idempotency, always-on speed hard cap
# --------------------------------------------------------------------------- #

_POS = SimpleNamespace(latitude_deg=36.1536, longitude_deg=-95.9932, relative_altitude_m=12.0)


def _px4(**cfg) -> PX4Backend:
    return PX4Backend(clock=time.time, config=PX4Config(**cfg))


def _prime(b: PX4Backend, *, speed: float = 0.0) -> None:
    now = time.time()
    vel = SimpleNamespace(north_m_s=speed, east_m_s=0.0, down_m_s=0.0)
    for key, val in (
        ("position", _POS), ("velocity", vel), ("in_air", True), ("armed", True),
    ):
        b._cache[key] = (val, now)


async def test_gimbal_ambiguous_retry_resends_until_accepted():
    """Doctrine refined by review #3: a gimbal attempt cancelled while the SDK
    call was still IN FLIGHT is ambiguous — the retry RE-SENDS (aiming is
    idempotent; the danger is marking done with zero angle commands, which is
    exactly what review #3's probe caught). Only a fully ACCEPTED attempt
    (SDK calls returned) reconciles without re-sending."""
    b = _px4()
    _prime(b)
    sends = {"n": 0}
    hang = asyncio.Event()

    class Gimbal:
        async def take_control(self, *a):
            sends["n"] += 1

        async def set_angles(self, *a):
            if sends["n"] == 1:
                await hang.wait()                      # first attempt: ambiguous

    b._system = SimpleNamespace(gimbal=Gimbal(), action=None)
    task = asyncio.ensure_future(b.set_gimbal_pitch(-20.0, idem="d121:g"))
    for _ in range(200):
        await asyncio.sleep(0.002)
        if sends["n"] == 1:
            break
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # executor retry, same key — ambiguous first attempt means RE-SEND...
    await asyncio.wait_for(b.set_gimbal_pitch(-20.0, idem="d121:g"), timeout=1.0)
    assert sends["n"] == 2, "ambiguous gimbal attempt must be re-sent"
    # ...and a THIRD call with the completed key is a pure no-op.
    await asyncio.wait_for(b.set_gimbal_pitch(-20.0, idem="d121:g"), timeout=1.0)
    assert sends["n"] == 2, "completed gimbal key must never re-send"


async def test_connect_wait_returns_once_critical_streams_complete():
    """D12.2 (found live by the Mac agent, 3/12 contract tests): fail-closed
    telemetry means connect() must WAIT for the first complete snapshot —
    'connected' has to mean 'I can answer basic state questions'."""
    b = _px4()

    async def feed():
        await asyncio.sleep(0.15)
        _prime(b)                                      # streams arrive late

    feeder = asyncio.ensure_future(feed())
    await asyncio.wait_for(b._await_first_snapshot(2.0), timeout=3.0)
    await feeder
    assert await b.latest_telemetry() is not None


async def test_connect_wait_fails_closed_naming_missing_streams():
    from core.interfaces import BackendUnavailable

    b = _px4()                                         # streams never arrive
    with pytest.raises(BackendUnavailable) as exc:
        await b._await_first_snapshot(0.3)
    assert "in_air" in str(exc.value)                  # says WHICH streams


async def test_speed_hard_cap_is_always_on_and_tight():
    """Rerun probe: requested 4 m/s, speed command 'succeeded', observed
    5.4 m/s — the old 1.25x+0.5 threshold (5.5) let it pass and monitoring
    was off when the ACK succeeded. The hard cap now always monitors."""
    b = _px4(command_wait_s=3.0)
    _prime(b, speed=5.4)                               # sustained overspeed
    b._home_abs_alt = 100.0
    sent = []

    async def set_speed(v):
        return None                                    # ACK succeeds... but lies

    async def goto_location(*a):
        sent.append(a)

    from core.schema import GeoPoint

    b._system = SimpleNamespace(
        action=SimpleNamespace(set_current_speed=set_speed, goto_location=goto_location)
    )
    with pytest.raises(CommandRejected):
        await b.goto(GeoPoint(lat=36.16, lon=-95.99), 20.0, 4.0, None, idem="d121:spd")
