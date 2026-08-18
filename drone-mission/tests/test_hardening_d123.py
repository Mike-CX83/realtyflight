"""D12.3 hardening regression tests — external review #3 absorbed.

Review #3's verdict: 5 verified / 2 partial / 3 broken, and "the simulator
path remains healthy." It confirmed every D12.1/D12.2 fix clean, then found a
deeper layer. Each test here pins one of the NEW confirmed defects, written to
FAIL on the D12.2 code:

- HOLD during fault recovery cancelled the recovery command and killed the
  mission task airborne with NO terminal state (review probe). Doctrine now:
  RECOVERY IS NOT HOLDABLE — hold() is state-aware and never preempts it.
- A hung backend.hold() ran outside the preemptible slot: a later ABORT could
  never interrupt it. The hold command now runs bounded IN the slot.
- A hung preflight was unbounded and un-abortable.
- RESUME pressed while not paused sat stale and instantly un-paused the next
  HOLD. Stale resumes are cleared at pause entry; resume() outside paused is
  recorded and ignored.
- A fabricated all-pass ValidationReport with the CORRECT plan hash and the
  full rule-ID manifest authorized a plan violating its own altitude limit.
  grant_approval() now re-runs the static rules itself — forgery dies on
  physics. (Live-tier proof needs the approval-service boundary: ledger'd.)
- Arriving inside tolerance beat the 3-strike overspeed debounce: a goto at
  6.1 m/s on a 5 m/s approval "succeeded" because arrival was checked while
  strikes were still accumulating. Arrival is now refused while overspeeding.
- A rejected PX4 freeze (abort_motion) was swallowed into a side file; the
  executor's freeze.unconfirmed could never fire. It now raises typed.
- A single future-dated critical field hid behind min(critical timestamps);
  future-dated aux fields (battery) passed as fresh.
- Gimbal marked its idempotency key in-flight BEFORE the SDK accepted the
  command — a cancel before acceptance made the retry a silent no-op.
- Dashboard /api/state mixed a NEW pending plan's identity with the OLD
  executor's progress.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from core.approval import ApprovalError, grant_approval
from core.engine import ExecutorTuning, MissionOutcome
from core.interfaces import CommandRejected
from core.policy.engine import required_rule_ids
from core.policy.types import RuleResult, ValidationReport
from core.schema import MissionPlan, compute_plan_hash
from tests.conftest import good_plan_dict
from tests.test_executor import build
from tests.test_hardening_d121 import _POS, _prime, _px4, _wait_event

TERMINAL_STATES = {"completed", "failed", "rejected", "manually_overridden"}
FASTREC = ExecutorTuning(timeout_factor=2.0, timeout_floor_s=0.25,
                         recovery_cmd_timeout_s=0.5)


# --------------------------------------------------------------------------- #
# Review C1 — HOLD is state-aware; recovery is NOT holdable
# --------------------------------------------------------------------------- #


async def test_hold_during_recovery_never_kills_the_mission(good_plan):
    """Review probe: HOLD during fault recovery raised CancelledError and left
    the drone AIRBORNE in 'returning' with no terminal state."""
    from backends.fake import FakeConfig

    mk, backend, log, clock = build(good_plan, cfg=FakeConfig(time_scale=0.05))
    backend.hooks[("goto", 3)] = "hang"               # hang mid-orbit
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    for _ in range(800):
        await asyncio.sleep(0.005)
        if sum(1 for a, _ in backend.command_log if a == "goto") >= 4:
            break
    ex.abort()                                        # recovery starts (slow RTL)
    await _wait_event(
        log, good_plan.mission_id,
        lambda e: e.type == "failsafe.dispatch" and e.payload.get("command") == "return_home",
    )
    ex.hold(operator="mike")                          # operator taps HOLD mid-recovery

    result = await asyncio.wait_for(task, timeout=5.0)   # must NOT raise/die
    assert result.outcome in (MissionOutcome.ABORTED, MissionOutcome.FAILED)
    assert ex.machine.current_state.id in TERMINAL_STATES
    types = [e.type for e in log.replay(good_plan.mission_id)]
    assert "hold.ignored" in types                    # recovery is not holdable


async def test_hung_hold_command_is_bounded_and_abortable(good_plan):
    """Review probe: backend.hold() hung outside the preemptible slot; a later
    ABORT left the mission stuck in 'paused' forever."""
    mk, backend, log, clock = build(good_plan, tuning=FASTREC)
    backend.hooks[("goto", 0)] = "hang"

    async def hung_hold():
        backend.command_log.append(("hold", "-"))
        await asyncio.sleep(3600)

    backend.hold = hung_hold
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_event(
        log, good_plan.mission_id,
        lambda e: e.type == "step.dispatched" and e.payload.get("step") == 1,
    )
    ex.hold(operator="mike")                          # preempts; hold cmd hangs
    await asyncio.sleep(0.1)
    ex.abort()                                        # must still work

    result = await asyncio.wait_for(task, timeout=5.0)
    assert result.outcome in (MissionOutcome.ABORTED, MissionOutcome.FAILED)
    assert ex.machine.current_state.id in TERMINAL_STATES


async def test_hung_preflight_is_bounded_and_terminal(good_plan):
    mk, backend, log, clock = build(good_plan, tuning=FASTREC)

    async def hung_preflight():
        await asyncio.sleep(3600)

    backend.preflight = hung_preflight
    ex = await mk()
    result = await asyncio.wait_for(ex.run(), timeout=5.0)
    assert result.outcome == MissionOutcome.REJECTED_AT_GATE
    assert "preflight" in result.reason
    assert backend.command_log == []


async def test_stale_resume_does_not_instantly_unpause(good_plan):
    """Review: RESUME set in any state stayed pending; the NEXT hold un-paused
    immediately. resume() outside paused is now ignored, and pause entry
    clears any stale resume."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_event(
        log, good_plan.mission_id,
        lambda e: e.type == "step.dispatched" and e.payload.get("step") == 1,
    )

    ex.resume(operator="mike")                        # stale: not paused yet
    ex.hold(operator="mike")
    for _ in range(400):
        await asyncio.sleep(0.005)
        if ex.machine.current_state.id == "paused":
            break
    assert ex.machine.current_state.id == "paused"
    await asyncio.sleep(0.2)                          # must STAY paused
    assert ex.machine.current_state.id == "paused", "stale RESUME un-paused the hold"

    ex.resume(operator="mike")                        # the real resume
    result = await asyncio.wait_for(task, timeout=5.0)
    assert result.outcome == MissionOutcome.COMPLETED


# --------------------------------------------------------------------------- #
# Review C2 — a correct-hash fabricated report dies on physics
# --------------------------------------------------------------------------- #


def test_fabricated_all_pass_report_with_correct_hash_is_rejected():
    """Review probe: takeoff 100 m vs mission limit 40 m, all-pass results for
    every required rule ID, CORRECT plan hash — grant_approval approved it.
    Approval now re-runs the static rules itself."""
    d = good_plan_dict()
    d["steps"][0]["alt_m"] = 100.0                    # schema-legal, rule-illegal
    plan = MissionPlan.model_validate(d)

    forged = ValidationReport(
        results=[
            RuleResult(rule=r, description="forged", passed=True, violations=[])
            for r in sorted(required_rule_ids(live=True))
        ],
        schema_ok=True,
        live_checked=True,
        plan_hash=compute_plan_hash(plan),            # the hash is CORRECT
    )
    with pytest.raises(ApprovalError) as exc:
        grant_approval(plan, forged, operator="mike", now_ts=time.time())
    assert "GEO-04" in str(exc.value)                 # physics, not paperwork


# --------------------------------------------------------------------------- #
# Review C4 — arrival cannot beat the overspeed monitor
# --------------------------------------------------------------------------- #


async def test_overspeed_at_arrival_is_refused():
    """Review probe: 6.1 m/s telemetry on a 5 m/s command, already inside
    arrival tolerance — goto returned success on the first poll."""
    b = _px4(command_wait_s=2.0)
    now = time.time()
    vel = SimpleNamespace(north_m_s=6.1, east_m_s=0.0, down_m_s=0.0)
    for key, val in (
        ("position", _POS), ("velocity", vel), ("in_air", True), ("armed", True),
    ):
        b._cache[key] = (val, now)
    b._home_abs_alt = 100.0

    async def set_speed(v):
        raise RuntimeError("DENIED")

    async def goto_location(*a):
        return None

    b._system = SimpleNamespace(
        action=SimpleNamespace(set_current_speed=set_speed, goto_location=goto_location)
    )
    from core.schema import GeoPoint

    target = GeoPoint(lat=_POS.latitude_deg, lon=_POS.longitude_deg)  # AT target
    with pytest.raises(CommandRejected):
        await b.goto(target, 12.0, 5.0, None, idem="d123:arr")


# --------------------------------------------------------------------------- #
# Review C5 — a rejected freeze is loud, in the MISSION audit
# --------------------------------------------------------------------------- #


async def test_px4_rejected_freeze_raises_typed():
    b = _px4()
    _prime(b)

    async def hold_fails():
        raise RuntimeError("DENIED: mode change refused")

    b._system = SimpleNamespace(action=SimpleNamespace(hold=hold_fails))
    with pytest.raises(CommandRejected):
        await b.abort_motion()


async def test_failed_freeze_lands_in_mission_audit(good_plan):
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"

    async def freeze_fails():
        backend.abort_motion_calls += 1
        raise CommandRejected("freeze (hold) rejected: DENIED")

    backend.abort_motion = freeze_fails
    ex = await mk()
    task = asyncio.ensure_future(ex.run())
    await _wait_event(
        log, good_plan.mission_id,
        lambda e: e.type == "step.dispatched" and e.payload.get("step") == 1,
    )
    ex.kill(reason="kill with dead freeze", operator="mike")
    result = await asyncio.wait_for(task, timeout=5.0)

    assert result.outcome == MissionOutcome.FAILED
    types = [e.type for e in log.replay(good_plan.mission_id)]
    assert "freeze.unconfirmed" in types              # the mission audit knows


# --------------------------------------------------------------------------- #
# Review Important-4 — per-field future timestamps fail closed (PX4)
# --------------------------------------------------------------------------- #


async def test_px4_future_dated_single_critical_field_fails_closed():
    b = _px4()
    now = time.time()
    vel = SimpleNamespace(north_m_s=0.0, east_m_s=0.0, down_m_s=0.0)
    b._cache["position"] = (_POS, now)
    b._cache["velocity"] = (vel, now)
    b._cache["armed"] = (True, now)
    b._cache["in_air"] = (True, now + 999.0)          # ONE field from the future
    assert await b.latest_telemetry() is None


async def test_px4_future_dated_aux_field_not_trusted():
    b = _px4()
    _prime(b)
    b._cache["battery"] = (SimpleNamespace(remaining_percent=77.0), time.time() + 999.0)
    tel = await b.latest_telemetry()
    assert tel is not None and tel.battery_pct == 0.0  # future battery = unknown


# --------------------------------------------------------------------------- #
# Review C3 — gimbal inflight marks AFTER acceptance
# --------------------------------------------------------------------------- #


async def test_gimbal_cancel_before_acceptance_resends():
    """Review probe: cancelled before the SDK accepted; retry was marked
    complete with zero angle commands. The inflight marker now lands only
    after the SDK calls return."""
    b = _px4()
    _prime(b)
    sends = {"n": 0}
    gate = asyncio.Event()

    class Gimbal:
        async def take_control(self, *a):
            sends["n"] += 1
            if sends["n"] == 1:
                await gate.wait()                     # never accepted

        async def set_angles(self, *a):
            return None

    b._system = SimpleNamespace(gimbal=Gimbal(), action=None)
    task = asyncio.ensure_future(b.set_gimbal_pitch(-20.0, idem="d123:g"))
    for _ in range(200):
        await asyncio.sleep(0.002)
        if sends["n"] == 1:
            break
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    await asyncio.wait_for(b.set_gimbal_pitch(-20.0, idem="d123:g"), timeout=1.0)
    assert sends["n"] == 2, "retry after unaccepted cancel must RE-SEND"


# --------------------------------------------------------------------------- #
# misc: derived recovery budget is exposed for the server's shutdown grace
# --------------------------------------------------------------------------- #


async def test_recovery_timeout_is_exposed_and_envelope_derived(good_plan):
    mk, backend, log, clock = build(good_plan)  # FAST tuning: explicit 2.0
    ex = await mk()
    assert ex.recovery_timeout_s == 2.0
    from core.engine import MissionExecutor
    from core.events import EventLog
    from core.policy.engine import validate_plan
    from core.policy.rules_wave4 import ValidationContext

    live = ValidationContext(
        now_ts=clock(), telemetry=await backend.latest_telemetry(),
        capabilities=backend.capabilities(),
    )
    approval = grant_approval(
        good_plan, validate_plan(good_plan, live), operator="mike", now_ts=clock()
    )
    ex2 = MissionExecutor(
        good_plan, approval, backend, EventLog(":memory:"), clock=clock
    )
    lim = good_plan.limits
    expected = 2.0 * lim.max_home_dist_m / max(lim.max_speed_ms, 0.5) \
        + lim.max_alt_m / 0.5 + 60.0
    assert abs(ex2.recovery_timeout_s - expected) < 1e-6
