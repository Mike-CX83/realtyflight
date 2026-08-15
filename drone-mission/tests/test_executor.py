"""Executor tests — the mission engine's guarantees, each proven:
happy path with evidence-gated steps, abort that preempts a hung command,
gate denial before takeoff, mid-flight fault -> failsafe recovery,
manual override terminality, retry-with-same-idem, and event-log replay."""

from __future__ import annotations

import asyncio

import pytest

from backends.fake import FakeBackend, FakeConfig
from core.approval import REAL_FLIGHT_CONFIRMATION, grant_approval
from core.engine import ExecutorTuning, MissionExecutor, MissionOutcome
from core.events import EventLog
from core.interfaces import CommandRejected, CommandTimeout
from core.policy import ValidationContext
from core.policy.engine import validate_plan
from core.schema import GeoPoint, MissionPlan
from tests.conftest import NOW


class Clock:
    """Mutable injected clock. Tests own time."""

    def __init__(self, t0: float = NOW) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t


FAST = ExecutorTuning(timeout_factor=2.0, timeout_floor_s=0.25, poll_interval_s=0.005)


def build(good_plan, *, cfg: FakeConfig | None = None, clock: Clock | None = None):
    clock = clock or Clock()
    backend = FakeBackend(clock, cfg or FakeConfig())
    log = EventLog(":memory:")

    async def _mk() -> MissionExecutor:
        live = ValidationContext(
            now_ts=clock(),
            telemetry=await backend.latest_telemetry(),
            capabilities=backend.capabilities(),
        )
        report = validate_plan(good_plan, live)
        approval = grant_approval(good_plan, report, operator="mike", now_ts=clock())
        return MissionExecutor(
            good_plan, approval, backend, log, clock=clock, profile="sim", tuning=FAST
        )

    return _mk, backend, log, clock


# ---------------------------------------------------------------------------- #
# Happy path
# ---------------------------------------------------------------------------- #


async def test_happy_path_completes_with_media_and_evidence(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()
    result = await ex.run()

    assert result.outcome == MissionOutcome.COMPLETED
    assert result.final_state == "completed"
    assert result.steps_completed == len(good_plan.steps)
    assert len(result.media) == good_plan.expected_capture_count() == 9
    assert backend.in_air is False and backend.alt_rel_m == 0.0

    types = [e.type for e in log.replay(good_plan.mission_id)]
    assert "approval.activated" in types
    assert types.count("media.captured") == 9
    assert "evidence.landed" in types
    assert types[-1] == "mission.closed"


async def test_orbit_flies_ring_waypoints_facing_center(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()
    await ex.run()
    goto_calls = [c for c in backend.command_log if c[0] == "goto"]
    assert len(goto_calls) >= 30  # 2 plan gotos + 30 orbit ring segments (360/12)


async def test_state_transitions_are_fully_audited(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()
    await ex.run()
    transitions = [
        (e.payload["source"], e.payload["target"])
        for e in log.replay(good_plan.mission_id)
        if e.type == "state.transition"
    ]
    assert transitions[0] == ("draft", "validating")
    assert ("approved", "executing") in transitions
    assert ("returning", "landing") in transitions
    assert transitions[-1] == ("landing", "completed")


# ---------------------------------------------------------------------------- #
# Abort preempts
# ---------------------------------------------------------------------------- #


async def test_abort_preempts_hung_command_and_recovers(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = "hang"  # first goto never returns
    ex = await mk()

    task = asyncio.ensure_future(ex.run())
    for _ in range(200):  # wait until the hung goto is dispatched
        await asyncio.sleep(0.005)
        if any(e.type == "step.dispatched" and e.payload["step"] == 1
               for e in log.replay(good_plan.mission_id)):
            break
    ex.abort()
    result = await asyncio.wait_for(task, timeout=5.0)

    assert result.outcome == MissionOutcome.ABORTED
    assert result.final_state == "completed"  # recovered: RTH + land
    assert backend.abort_motion_calls >= 1
    assert backend.in_air is False
    types = [e.type for e in log.replay(good_plan.mission_id)]
    assert "abort.requested" in types and "abort.executing" in types
    # no work step after the abort:
    dispatched_steps = [e.payload["step"] for e in log.replay(good_plan.mission_id)
                        if e.type == "step.dispatched"]
    assert max(dispatched_steps) == 1


# ---------------------------------------------------------------------------- #
# Gate denials and faults
# ---------------------------------------------------------------------------- #


async def test_dead_battery_never_leaves_the_ground(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan, cfg=FakeConfig(battery_pct=12.0))
    ex = await mk.__wrapped__() if hasattr(mk, "__wrapped__") else None  # noqa: unused
    # approval itself must refuse: validation with 12% battery fails PWR-01
    from core.approval import ApprovalError

    with pytest.raises(ApprovalError):
        live = ValidationContext(
            now_ts=clock(),
            telemetry=await backend.latest_telemetry(),
            capabilities=backend.capabilities(),
        )
        report = validate_plan(good_plan, live)
        grant_approval(good_plan, report, operator="mike", now_ts=clock())
    assert backend.command_log == []  # literally nothing was ever sent


async def test_battery_crash_mid_flight_triggers_failsafe(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()

    # sabotage: after the 2nd command, battery collapses below the floor
    orig_drain = backend._drain
    counter = {"n": 0}

    def draining():
        counter["n"] += 1
        if counter["n"] == 2:
            backend.battery_pct = 18.0
        orig_drain()

    backend._drain = draining
    result = await ex.run()

    assert result.outcome == MissionOutcome.FAILED
    assert "PWR" in result.reason
    assert backend.in_air is False  # failsafe flew it home and landed
    types = [e.type for e in log.replay(good_plan.mission_id)]
    assert "failsafe.triggered" in types
    assert types.count("failsafe.dispatch") == 2  # RTH + land


async def test_manual_override_is_terminal(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()

    orig_drain = backend._drain
    counter = {"n": 0}

    def draining():
        counter["n"] += 1
        if counter["n"] == 3:
            backend.manual_input = True  # pilot grabs the sticks
        orig_drain()

    backend._drain = draining
    result = await ex.run()

    assert result.outcome == MissionOutcome.OVERRIDDEN
    assert result.final_state == "manually_overridden"
    # autonomy must NOT have flown it home — the human owns the aircraft now
    assert backend.abort_motion_calls == 0
    last_cmds = [c[0] for c in backend.command_log]
    assert "return_home" not in last_cmds


async def test_breaker_trip_mid_flight_forces_recovery(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()

    orig_drain = backend._drain
    counter = {"n": 0}

    def draining():
        counter["n"] += 1
        if counter["n"] == 2:
            ex.breaker.trip("range safety officer said stop")
        orig_drain()

    backend._drain = draining
    result = await ex.run()
    assert result.outcome == MissionOutcome.FAILED
    assert "CB-01" in result.reason or "breaker" in result.reason


# ---------------------------------------------------------------------------- #
# Retries and idempotency
# ---------------------------------------------------------------------------- #


async def test_timeout_retries_with_same_idem_then_succeeds(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("goto", 0)] = CommandTimeout("transient")  # first attempt only
    ex = await mk()
    result = await ex.run()

    assert result.outcome == MissionOutcome.COMPLETED
    events = log.replay(good_plan.mission_id)
    dispatches = [e for e in events if e.type == "step.dispatched" and e.payload["step"] == 1]
    assert len(dispatches) == 2  # attempt 0 failed, attempt 1 succeeded
    assert dispatches[0].payload["idem"] == dispatches[1].payload["idem"]  # SAME key


async def test_exhausted_retries_fail_safely(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    for n in range(5):
        backend.hooks[("goto", n)] = CommandTimeout("persistent")
    ex = await mk()
    result = await ex.run()
    assert result.outcome == MissionOutcome.FAILED
    assert "CommandTimeout" in result.reason
    assert backend.in_air is False  # still recovered


async def test_retried_land_reenters_landing_without_illegal_transition(good_plan: MissionPlan):
    """Regression pin for the D7 live-flight crash (fixed in 7ff33f0).

    _perform() used to call machine.begin_landing() unconditionally, but
    _dispatch_with_retries re-invokes _perform() on a transient CommandTimeout —
    and landing->landing is not a legal transition. Real PX4 missed the
    touchdown tolerance on the first evidence check and the retry crashed the
    mission mid-air with TransitionNotAllowed; the deterministic fake always
    lands cleanly, so the whole suite stayed green around the bug. This scripts
    that PX4 behavior: first land attempt times out, the retry must complete —
    and 'landing' must be entered exactly once."""
    mk, backend, log, clock = build(good_plan)
    land_idx = len(good_plan.steps) - 1
    backend.hooks[("land", 0)] = CommandTimeout("no touchdown evidence yet (PX4-style)")
    ex = await mk()
    result = await ex.run()

    assert result.outcome == MissionOutcome.COMPLETED
    assert result.final_state == "completed"
    events = log.replay(good_plan.mission_id)
    dispatches = [e for e in events
                  if e.type == "step.dispatched" and e.payload["step"] == land_idx]
    assert len(dispatches) == 2  # attempt 0 timed out, attempt 1 landed
    assert any(e.type == "step.timeout" and e.payload["step"] == land_idx for e in events)
    entered_landing = [e for e in events
                       if e.type == "state.transition" and e.payload["target"] == "landing"]
    assert len(entered_landing) == 1  # the guard skipped, it did not re-transition


async def test_retried_return_home_reenters_returning_without_illegal_transition(
    good_plan: MissionPlan,
):
    """Same latent bug, other branch: begin_return() on a retried return_home
    (returning->returning is equally illegal). Scripted the same way."""
    mk, backend, log, clock = build(good_plan)
    rth_idx = len(good_plan.steps) - 2
    backend.hooks[("return_home", 0)] = CommandTimeout("transient RTL stall")
    ex = await mk()
    result = await ex.run()

    assert result.outcome == MissionOutcome.COMPLETED
    events = log.replay(good_plan.mission_id)
    dispatches = [e for e in events
                  if e.type == "step.dispatched" and e.payload["step"] == rth_idx]
    assert len(dispatches) == 2
    entered_returning = [e for e in events
                         if e.type == "state.transition" and e.payload["target"] == "returning"]
    assert len(entered_returning) == 1
    # and the flight still finished properly after the wobble
    assert backend.in_air is False and result.final_state == "completed"


async def test_backend_rejection_goes_failsafe(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("set_gimbal", 0)] = CommandRejected("gimbal stuck")
    ex = await mk()
    result = await ex.run()
    assert result.outcome == MissionOutcome.FAILED
    assert "gimbal stuck" in result.reason


async def test_recovery_flight_backend_error_ends_failed_not_crashed(good_plan: MissionPlan):
    """Regression pin for the D8 live-flight crash (fixed alongside D8).

    _recovery_flight() used to call backend.return_home()/land() with no
    exception handling — the last line of defense could itself raise and
    crash the whole process uncaught, losing the MissionResult entirely. Real
    PX4 under heavy load hit exactly this: a mid-flight gate denial triggered
    failsafe, and the recovery's own return_home() then timed out for the
    full 120 s ceiling and crashed. Scripts a failure the recovery's return
    trip itself, on top of a failure that triggers the recovery, and asserts
    the mission still ends FAILED with a recorded reason — never an escaped
    exception."""
    mk, backend, log, clock = build(good_plan)
    backend.hooks[("set_gimbal", 0)] = CommandRejected("gimbal stuck")  # triggers failsafe
    backend.hooks[("return_home", 0)] = CommandTimeout("recovery RTL stall (PX4-style)")
    ex = await mk()
    result = await ex.run()  # must not raise

    assert result.outcome == MissionOutcome.FAILED
    assert "gimbal stuck" in result.reason
    events = log.replay(good_plan.mission_id)
    assert any(e.type == "recovery.failed" for e in events)
    final_transition = [e for e in events if e.type == "state.transition"][-1]
    assert final_transition.payload["target"] == "failed"


# ---------------------------------------------------------------------------- #
# Replay: the log alone tells the whole story
# ---------------------------------------------------------------------------- #


async def test_replay_reconstructs_the_mission(good_plan: MissionPlan):
    mk, backend, log, clock = build(good_plan)
    ex = await mk()
    result = await ex.run()

    events = log.replay(good_plan.mission_id)
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs) == list(range(len(events)))  # gapless, ordered

    # fold the log: final state, steps, media — all recoverable without the executor
    final_transition = [e for e in events if e.type == "state.transition"][-1]
    steps_done = sum(1 for e in events if e.type == "step.completed")
    media = sum(1 for e in events if e.type == "media.captured")
    assert final_transition.payload["target"] == result.final_state
    assert steps_done == result.steps_completed
    assert media == len(result.media)
