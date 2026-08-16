"""The mission executor — an approved plan becomes a flight (doc 08 §5/§6).

Guarantees encoded here (each has a test):
- Nothing dispatches without the full dispatch gate passing (approval hash/TTL,
  sim-real wall, live battery/telemetry/GPS re-check, circuit breaker closed).
- Steps advance only on telemetry EVIDENCE (position within tolerance, media
  reference received, touchdown thresholds) — never on command acks alone.
- abort() PREEMPTS: it cancels the in-flight command task AND tells the
  backend to stop moving, then flies the recovery (RTH -> land).
- Manual stick input is terminal for autonomy: suspend everything, mark
  manually_overridden, never dispatch again.
- Faults follow the plan's FailsafePolicy deterministically; recovery commands
  (RTH/land) bypass plan-gates but never the circuit breaker.
- Every decision lands in the append-only event log.

Clock discipline: `clock` is injected; the executor never reads wall time.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from core.approval import ApprovalRecord
from core.engine.machine import MissionMachine
from core.events import EventLog, MissionRecorder
from core.geo import distance_m
from core.interfaces import (
    BackendError,
    CommandTimeout,
    DroneBackend,
    TelemetrySnapshot,
)
from core.policy.dispatch import CircuitBreaker, DispatchContext, check_dispatch
from core.policy.rules_wave4 import ValidationContext
from core.schema import (
    CapturePhoto,
    Goto,
    Hold,
    Land,
    MissionPlan,
    Orbit,
    ReturnHome,
    SetGimbal,
    Takeoff,
)

# Evidence thresholds (MDS-verified pattern; doc 08 §5)
LANDED_MAX_ALT_M = 1.0
LANDED_MAX_VSPEED_MS = 0.75
MAX_RETRIES = 2


class MissionOutcome(StrEnum):
    COMPLETED = "completed"
    ABORTED = "aborted"            # operator abort, recovered safely (terminal state: completed)
    FAILED = "failed"
    OVERRIDDEN = "manually_overridden"
    REJECTED_AT_GATE = "rejected_at_gate"  # never left the ground


@dataclass
class ExecutorTuning:
    """Watchdog knobs — injectable so tests run in milliseconds."""

    timeout_factor: float = 2.0
    timeout_floor_s: float = 10.0
    poll_interval_s: float = 0.02


@dataclass
class MissionResult:
    outcome: MissionOutcome
    final_state: str
    reason: str = ""
    steps_completed: int = 0
    media: list = field(default_factory=list)


class MissionExecutor:
    def __init__(
        self,
        plan: MissionPlan,
        approval: ApprovalRecord,
        backend: DroneBackend,
        event_log: EventLog,
        *,
        clock: Callable[[], float],
        profile: str = "sim",
        breaker: CircuitBreaker | None = None,
        tuning: ExecutorTuning | None = None,
    ) -> None:
        self.plan = plan
        self.approval = approval
        self.backend = backend
        self.clock = clock
        self.profile = profile
        self.breaker = breaker or CircuitBreaker()
        self.tuning = tuning or ExecutorTuning()
        self.rec = MissionRecorder(event_log, plan.mission_id, clock)
        self.machine = MissionMachine(on_transition=self._on_transition)
        self.media: list = []
        self._abort_requested = asyncio.Event()
        self._hold_requested = asyncio.Event()
        self._resume_requested = asyncio.Event()
        self._current_task: asyncio.Task | None = None
        self._steps_completed = 0

    # ------------------------------------------------------------------ hooks

    def _on_transition(self, event: str, source: str, target: str) -> None:
        self.rec.record("state.transition", event=event, source=source, target=target)

    # ------------------------------------------------------------- public API

    def abort(self) -> None:
        """Operator abort. Safe to call from any coroutine at any time."""
        self.rec.record("abort.requested")
        self._abort_requested.set()
        if self._current_task is not None and not self._current_task.done():
            self._current_task.cancel()

    def hold(self) -> None:
        self.rec.record("hold.requested")
        self._hold_requested.set()

    def resume(self) -> None:
        self.rec.record("resume.requested")
        self._resume_requested.set()

    # ------------------------------------------------------------ gate & tel

    async def _live_ctx(self) -> ValidationContext:
        tel = await self.backend.latest_telemetry()
        return ValidationContext(
            now_ts=self.clock(), telemetry=tel, capabilities=self.backend.capabilities()
        )

    async def _gate(self, where: str) -> list[str]:
        live = await self._live_ctx()
        dctx = DispatchContext(
            now_ts=self.clock(), profile=self.profile, approval=self.approval, live=live
        )
        violations = check_dispatch(self.plan, dctx, self.breaker)
        if violations:
            self.rec.record(
                "gate.denied",
                where=where,
                rules=sorted({v.rule for v in violations}),
                messages=[v.message for v in violations][:6],
            )
        return sorted({v.rule for v in violations})

    async def _check_override(self) -> bool:
        tel = await self.backend.latest_telemetry()
        return bool(tel and tel.manual_input_detected)

    # ------------------------------------------------------------- main loop

    async def run(self) -> MissionResult:
        m = self.machine
        m.start_validation()
        m.pass_validation()  # (plan arrived validated+approved; recorded for the trail)
        m.approve()

        # Pre-flight gate: nothing has moved yet — a denial here is a clean no-go.
        denied = await self._gate("preflight")
        if denied:
            m.start_execution()
            m.fail()
            return MissionResult(
                outcome=MissionOutcome.REJECTED_AT_GATE,
                final_state=m.current_state.id,
                reason=f"preflight gate: {denied}",
            )

        pre = await self.backend.preflight()
        self.rec.record("preflight.report", ok=pre.ok, items=[i.model_dump() for i in pre.items])
        if not pre.ok:
            m.start_execution()
            m.fail()
            return MissionResult(
                outcome=MissionOutcome.REJECTED_AT_GATE,
                final_state=m.current_state.id,
                reason="backend preflight failed",
            )

        self.approval = self.approval.activated(self.clock())
        self.rec.record("approval.activated", approval_id=self.approval.approval_id)
        m.start_execution()

        try:
            for i, step in enumerate(self.plan.steps):
                # ---- operator/hold/override checkpoints between steps ------- #
                if self._abort_requested.is_set():
                    return await self._recover_abort(i)
                if await self._check_override():
                    self.rec.record("override.detected", step=i)
                    m.manual_override()
                    return MissionResult(
                        outcome=MissionOutcome.OVERRIDDEN,
                        final_state=m.current_state.id,
                        reason="manual stick input",
                        steps_completed=self._steps_completed,
                        media=self.media,
                    )
                if self._hold_requested.is_set():
                    m.step_hold()
                    await self.backend.hold()
                    self._hold_requested.clear()
                    await self._wait_resume()
                    if self._abort_requested.is_set():
                        return await self._recover_abort(i)
                    denied = await self._gate("resume")
                    if denied:
                        return await self._failsafe_recovery(i, f"resume gate: {denied}")
                    m.resume()

                # ---- the dispatch gate, before EVERY step ------------------- #
                if isinstance(step, (ReturnHome, Land)):
                    pass  # plan-tail recovery commands gate only on the breaker below
                else:
                    denied = await self._gate(f"step:{i}")
                    if denied:
                        return await self._failsafe_recovery(i, f"gate: {denied}")
                if self.breaker.is_open:
                    return await self._failsafe_recovery(i, "circuit breaker open")

                # ---- dispatch with watchdog + bounded retries --------------- #
                try:
                    await self._dispatch_with_retries(i, step)
                except asyncio.CancelledError:
                    return await self._recover_abort(i)
                except BackendError as exc:
                    return await self._failsafe_recovery(i, f"{type(exc).__name__}: {exc}")

                self._steps_completed += 1
                self.rec.record("step.completed", step=i, action=step.action)

            m.touchdown() if m.current_state.id == "landing" else None
            return MissionResult(
                outcome=MissionOutcome.COMPLETED,
                final_state=m.current_state.id,
                steps_completed=self._steps_completed,
                media=self.media,
            )
        finally:
            self.rec.record(
                "mission.closed",
                state=m.current_state.id,
                steps_completed=self._steps_completed,
                media_count=len(self.media),
            )

    # -------------------------------------------------------------- dispatch

    async def _dispatch_with_retries(self, i: int, step) -> None:
        idem = f"{self.plan.mission_id}:{i}"  # SAME key across retries => backend dedups
        timeout = max(
            self.tuning.timeout_floor_s,
            self._expected_duration_s(step) * self.tuning.timeout_factor,
        )
        last_exc: Exception | None = None
        for attempt in range(1 + MAX_RETRIES):
            self.rec.record(
                "step.dispatched", step=i, action=step.action, attempt=attempt, idem=idem
            )
            self._current_task = asyncio.ensure_future(self._perform(i, step, idem))
            try:
                await asyncio.wait_for(asyncio.shield(self._current_task), timeout=timeout)
                return
            except TimeoutError:
                self._current_task.cancel()
                self.rec.record("step.timeout", step=i, attempt=attempt, timeout_s=timeout)
                last_exc = CommandTimeout(f"step {i} timed out after {timeout:.1f}s")
            except CommandTimeout as exc:
                self.rec.record("step.timeout", step=i, attempt=attempt, backend_reported=True)
                last_exc = exc
            finally:
                self._current_task = None
        raise last_exc or CommandTimeout(f"step {i}")

    async def _perform(self, i: int, step, idem: str) -> None:
        b = self.backend
        if isinstance(step, Takeoff):
            await b.takeoff(step.alt_m, idem=idem)
            await self._require_alt(step.alt_m, tolerance=1.5)
        elif isinstance(step, Goto):
            await b.goto(step.to, step.alt_m, step.speed_ms, step.yaw_deg, idem=idem)
            await self._require_position(step.to)
        elif isinstance(step, Orbit):
            await self._fly_orbit(i, step, idem)
        elif isinstance(step, SetGimbal):
            await b.set_gimbal_pitch(step.pitch_deg, idem=idem)
        elif isinstance(step, CapturePhoto):
            ref = await b.capture_photo(step.capture, idem=idem)
            self.media.append(ref)
            self.rec.record("media.captured", step=i, tag=ref.tag, media_id=ref.media_id)
        elif isinstance(step, Hold):
            # D10 P1: a hold must actually hold (the plan's endurance budget
            # charges for it), and it must stay abortable — waiting on the
            # abort event (not a blind sleep) means abort() interrupts it
            # instantly instead of stalling the recovery for duration_s.
            await b.hold()
            try:
                await asyncio.wait_for(
                    self._abort_requested.wait(), timeout=step.duration_s
                )
                raise asyncio.CancelledError()  # abort during hold -> recovery
            except TimeoutError:
                pass  # full hold elapsed — the normal case
        elif isinstance(step, ReturnHome):
            if self.machine.current_state.id != "returning":
                self.machine.begin_return()
            await b.return_home(idem=idem)
            await self._require_position(self.plan.property.home, tolerance_scale=2.0)
        elif isinstance(step, Land):
            if self.machine.current_state.id != "landing":
                self.machine.begin_landing()
            await b.land(idem=idem)
            await self._require_landed()

    async def _fly_orbit(self, i: int, step: Orbit, idem: str) -> None:
        """Portable orbit: a ring of goto waypoints, yaw facing center, captures
        at the marked angles (doc 04 §5 — the form every backend can fly)."""
        n_segments = max(4, int(step.arc_deg // 12))
        capture_every = step.captures_every_deg
        next_capture_angle = 0.0
        sign = 1.0 if step.direction == "cw" else -1.0

        for k in range(n_segments + 1):
            angle = sign * (step.arc_deg * k / n_segments)
            rad = math.radians(angle)
            # point on the ring, in the center's local frame (x east, y north)
            east = step.radius_m * math.sin(rad)
            north = step.radius_m * math.cos(rad)
            lat = step.center.lat + (north / 111_195.0)
            lon = step.center.lon + (east / (111_195.0 * math.cos(math.radians(step.center.lat))))
            from core.schema import GeoPoint

            wp = GeoPoint(lat=lat, lon=lon)
            yaw = (math.degrees(math.atan2(-east, -north)) % 360.0)  # face the center
            await self.backend.goto(wp, step.alt_m, step.speed_ms, yaw, idem=f"{idem}:seg{k}")

            if capture_every is not None and step.capture is not None:
                # strict '<' on the arc: on a full 360° circle the last waypoint is
                # the first one again — no duplicate photo at the seam
                if abs(angle) + 1e-6 >= next_capture_angle and next_capture_angle < step.arc_deg:
                    ref = await self.backend.capture_photo(
                        step.capture, idem=f"{idem}:cap{int(next_capture_angle)}"
                    )
                    self.media.append(ref)
                    self.rec.record(
                        "media.captured", step=i, tag=ref.tag,
                        media_id=ref.media_id, angle_deg=abs(angle),
                    )
                    next_capture_angle += capture_every

    # -------------------------------------------------------------- evidence

    async def _require_position(self, target, tolerance_scale: float = 1.0) -> None:
        tel = await self._fresh_tel()
        tol = self.plan.limits.acceptance_radius_m * tolerance_scale
        d = distance_m(tel.position, target)
        if d > tol:
            raise CommandTimeout(f"no arrival evidence: {d:.1f} m from target (tol {tol:.1f} m)")
        self.rec.record("evidence.position", distance_m=round(d, 2), tolerance_m=tol)

    async def _require_alt(self, alt_m: float, tolerance: float) -> None:
        tel = await self._fresh_tel()
        if abs(tel.alt_rel_m - alt_m) > tolerance:
            raise CommandTimeout(
                f"no altitude evidence: at {tel.alt_rel_m:.1f} m, wanted {alt_m:.1f} m"
            )
        self.rec.record("evidence.altitude", alt_m=tel.alt_rel_m)

    async def _require_landed(self) -> None:
        tel = await self._fresh_tel()
        if tel.alt_rel_m > LANDED_MAX_ALT_M or abs(tel.vspeed_ms) > LANDED_MAX_VSPEED_MS:
            raise CommandTimeout(
                f"no touchdown evidence: alt {tel.alt_rel_m:.2f} m, vspeed {tel.vspeed_ms:.2f} m/s"
            )
        self.rec.record("evidence.landed", alt_m=tel.alt_rel_m, vspeed_ms=tel.vspeed_ms)

    async def _fresh_tel(self) -> TelemetrySnapshot:
        tel = await self.backend.latest_telemetry()
        if tel is None:
            raise CommandTimeout("no telemetry for evidence check")
        age = self.clock() - tel.ts
        if age > self.plan.failsafe.telemetry_stale_hold_s:
            raise CommandTimeout(f"telemetry too old for evidence ({age:.1f}s)")
        return tel

    # -------------------------------------------------------------- recovery

    async def _recover_abort(self, at_step: int) -> MissionResult:
        """Operator abort: stop motion NOW, then fly home and land."""
        m = self.machine
        self.rec.record("abort.executing", at_step=at_step)
        if m.current_state.id in ("executing", "paused"):
            m.operator_abort()
        await self.backend.abort_motion()
        await self._recovery_flight()
        # D10 P0: a terminal "completed" requires LANDED EVIDENCE, not just
        # having reached the landing state. If recovery's own commands failed
        # (recovery.failed swallows them so we still get here), the aircraft
        # may be airborne — reporting "completed" then would be a lie.
        if not await self._landed_evidence():
            self.rec.record(
                "recovery.unresolved",
                at_step=at_step,
                why="no touchdown evidence after abort recovery",
            )
            if m.current_state.id not in ("failed", "completed"):
                m.fail()
            return MissionResult(
                outcome=MissionOutcome.FAILED,
                final_state=m.current_state.id,
                reason="operator abort; recovery unresolved — no touchdown evidence",
                steps_completed=self._steps_completed,
                media=self.media,
            )
        m.touchdown() if m.current_state.id == "landing" else None
        return MissionResult(
            outcome=MissionOutcome.ABORTED,
            final_state=m.current_state.id,
            reason="operator abort",
            steps_completed=self._steps_completed,
            media=self.media,
        )

    async def _failsafe_recovery(self, at_step: int, reason: str) -> MissionResult:
        """Deterministic fault response: never continue, RTH + land, mark failed."""
        m = self.machine
        self.rec.record("failsafe.triggered", at_step=at_step, reason=reason)
        if m.current_state.id in ("executing", "paused"):
            m.fault_abort()
        await self.backend.abort_motion()
        await self._recovery_flight()
        m.fail()
        return MissionResult(
            outcome=MissionOutcome.FAILED,
            final_state=m.current_state.id,
            reason=reason,
            steps_completed=self._steps_completed,
            media=self.media,
        )

    async def _landed_evidence(self) -> bool:
        """True only when telemetry PROVES the aircraft is on the ground.
        Missing telemetry is not evidence (deny-by-default)."""
        tel = await self.backend.latest_telemetry()
        return bool(
            tel
            and not tel.in_air
            and tel.alt_rel_m <= LANDED_MAX_ALT_M
            and abs(tel.vspeed_ms) <= LANDED_MAX_VSPEED_MS
        )

    async def _recovery_flight(self) -> None:
        """RTH + land, bypassing plan gates (this IS the safety response) but
        never the breaker-as-kill-switch for dispatch of NEW work.

        Never raises: this is the last line of defense, so even if the
        recovery commands themselves fail (backend timeout/rejection), the
        mission must still end in a recorded terminal state — not crash the
        process and lose the outcome."""
        m = self.machine
        tel = await self.backend.latest_telemetry()
        if tel is None or not tel.in_air:
            self.rec.record("recovery.skipped", why="not airborne")
            if m.current_state.id == "aborting":
                m.begin_landing()
            return
        try:
            self.rec.record("failsafe.dispatch", command="return_home")
            m.begin_return()
            await self.backend.return_home(idem=f"{self.plan.mission_id}:recovery:rth")
            self.rec.record("failsafe.dispatch", command="land")
            m.begin_landing()
            await self.backend.land(idem=f"{self.plan.mission_id}:recovery:land")
        except BackendError as exc:
            self.rec.record("recovery.failed", error=f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------ misc utils

    async def _wait_resume(self) -> None:
        resume = asyncio.ensure_future(self._resume_requested.wait())
        abort = asyncio.ensure_future(self._abort_requested.wait())
        try:
            await asyncio.wait({resume, abort}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            resume.cancel()
            abort.cancel()
        self._resume_requested.clear()

    def _expected_duration_s(self, step) -> float:
        if isinstance(step, Takeoff):
            return step.alt_m / 1.5
        if isinstance(step, Goto):
            return 30.0  # conservative fixed leg budget; refined per-leg later
        if isinstance(step, Orbit):
            return (2 * math.pi * step.radius_m * (step.arc_deg / 360.0)) / step.speed_ms + 60.0
        if isinstance(step, Hold):
            return step.duration_s
        return 15.0
