"""D7 — the M3 demo wiring: one typed sentence flies the whole governed pipeline.

    # the real thing (SITL running, API key in drone-mission/.env or exported):
    python -m demo.fly "Photograph this property: full exterior package." --backend px4

    # keyless dry run (no API, no simulator, deterministic scripted 'LLM'):
    python -m demo.fly --backend fake --model scripted --auto-approve

Pipeline, end to end (CLAUDE.md target architecture — every layer is the real one):

  natural language
      -> MissionPlanner        LLM authors steps+summary ONLY; envelope is ours
      -> static validation     Waves 1-3, inside the planner's repair loop
      -> LIVE validation       Wave 4 against real telemetry + capabilities
      -> human approval        hash-bound, 300 s TTL, sim profile (Wave 5)
      -> MissionExecutor       state machine, dispatch gate before every step,
                               telemetry-evidence progress, bounded retries
      -> DroneBackend          fake | px4 (MAVSDK -> PX4 SITL -> Gazebo physics)
      -> append-only EventLog  the audit trail, replayed to the screen at the end

Ctrl+C during flight = operator ABORT: the executor preempts the in-flight
command and flies return-home + land. That is a feature demo, not a crash.

Exit codes: 0 completed | 1 flight failed/aborted | 2 planner could not produce
a valid plan | 3 live validation or approval refused | 4 operator denied |
5 backend unreachable.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import math
import os
import signal
import sys
import time
from pathlib import Path

from backends.fake import FakeBackend, FakeConfig
from core.approval import ApprovalError, grant_approval
from core.engine import MissionExecutor, MissionOutcome
from core.events import EventLog
from core.geo import distance_m
from core.policy.engine import validate_plan
from core.policy.rules_wave4 import ValidationContext, estimate_mission_duration_s
from core.schema import (
    FailsafePolicy,
    GeoPoint,
    Limits,
    MissionPlan,
    Property,
    compute_plan_hash,
)
from planner import MissionPlanner, PlanRequest

DEFAULT_REQUEST = (
    "Photograph this property: orbit the house and give me a full exterior package."
)

# --------------------------------------------------------------------------- #
# Environment / model selection (same conventions as planner/demo.py)
# --------------------------------------------------------------------------- #


def _load_dotenv() -> None:
    """Tiny .env loader (repo root or cwd) — keys stay on disk, gitignored,
    never in shell history. Real env vars win over the file."""
    for candidate in (Path(__file__).resolve().parents[1] / ".env", Path(".env")):
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
            return


def pick_model(arg: str | None) -> str | None:
    """--model wins; then PLANNER_MODEL; then whichever API key exists."""
    if arg:
        return arg  # includes the special value "scripted"
    if os.environ.get("PLANNER_MODEL"):
        return os.environ["PLANNER_MODEL"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic:claude-sonnet-4-5"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai:gpt-5.1"
    return None


def scripted_model(prop: Property):
    """A deterministic stand-in 'LLM' for keyless dry runs: emits the canonical
    exterior package (same shape the planner tests use). The point of the demo
    is the PIPELINE — this lets you run it end-to-end with zero credentials."""
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    center = {"lat": prop.center.lat, "lon": prop.center.lon}
    draft = {
        "summary": "Exterior package: elevated orbit of the structure with 8 bracketed "
        "captures, one straight-down lot shot, then home and land. [scripted demo model]",
        "steps": [
            {"action": "takeoff", "alt_m": 22.0},
            {"action": "set_gimbal", "pitch_deg": -25.0},
            {
                "action": "orbit",
                "center": center,
                "radius_m": 20.0,
                "alt_m": 22.0,
                "speed_ms": 3.0,
                "arc_deg": 360.0,
                "direction": "cw",
                "captures_every_deg": 45.0,
                "capture": {"mode": "bracket3", "tag": "exterior_orbit"},
            },
            {"action": "goto", "to": center, "alt_m": 38.0, "speed_ms": 3.0},
            {"action": "set_gimbal", "pitch_deg": -90.0},
            {"action": "capture_photo", "capture": {"mode": "single", "tag": "lot_overhead"}},
            {"action": "return_home"},
            {"action": "land"},
        ],
    }

    def fn(messages, info: AgentInfo) -> ModelResponse:
        tool = (info.output_tools or [])[0].name
        return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=draft)])

    return FunctionModel(fn)


# --------------------------------------------------------------------------- #
# Backend + property setup
# --------------------------------------------------------------------------- #


async def make_backend(kind: str, time_scale: float, connect_timeout_s: float):
    if kind == "fake":
        backend = FakeBackend(clock=time.time, config=FakeConfig(time_scale=time_scale))
        await backend.connect()
        return backend

    from backends.px4_mavsdk import PX4Backend, PX4Config

    backend = PX4Backend(clock=time.time, config=PX4Config())
    print(f"connecting to PX4 SITL ({backend.cfg.system_address})...")
    try:
        await asyncio.wait_for(backend.connect(), timeout=connect_timeout_s)
    except TimeoutError:
        raise SystemExit(
            "\nCould not reach PX4 SITL. Start the simulator first:\n"
            "  docker run --rm -it jonasvautherin/px4-gazebo-headless:1.17.0\n"
            "then re-run this demo. (exit 5)"
        ) from None
    return backend


async def first_telemetry(backend, timeout_s: float = 30.0):
    """Wait for the first real telemetry snapshot (PX4 streams take a moment)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        tel = await backend.latest_telemetry()
        if tel is not None:
            return tel
        await asyncio.sleep(0.25)
    raise SystemExit("no telemetry from the backend after connect — is the sim healthy? (exit 5)")


def property_around(home: GeoPoint, center_north_m: float = 45.0, half_m: float = 75.0) -> Property:
    """The demo property: a square drawn around wherever the drone actually is.

    In the product, the operator draws this on a satellite map (M3 dashboard).
    Here we synthesize it from the backend's real home position so the same
    demo works in Tulsa (fake) and Zurich (PX4 SITL default) alike — the
    'structure' center sits ~45 m north of the launch point.
    """
    m_per_deg_lat = 111_195.0
    m_per_deg_lon = 111_195.0 * math.cos(math.radians(home.lat))
    center = GeoPoint(lat=home.lat + center_north_m / m_per_deg_lat, lon=home.lon)
    dlat, dlon = half_m / m_per_deg_lat, half_m / m_per_deg_lon
    boundary = [
        GeoPoint(lat=center.lat + dlat, lon=center.lon - dlon),
        GeoPoint(lat=center.lat + dlat, lon=center.lon + dlon),
        GeoPoint(lat=center.lat - dlat, lon=center.lon + dlon),
        GeoPoint(lat=center.lat - dlat, lon=center.lon - dlon),
    ]
    return Property(center=center, boundary=boundary, home=home)


# --------------------------------------------------------------------------- #
# Console output helpers
# --------------------------------------------------------------------------- #


def print_report(report, *, title: str) -> None:
    print(f"\n--- {title} ---")
    for r in report.results:
        mark = "ok " if r.passed else "FAIL"
        print(f"  [{mark}] {r.rule}: {r.description}")
        for v in r.violations:
            print(f"         -> {v.message}")


def print_plan(plan: MissionPlan) -> None:
    print(f"\nSUMMARY: {plan.summary}\n\nSTEPS:")
    for i, s in enumerate(plan.steps):
        print(f"  {i:2d}. {s.model_dump(exclude_none=True)}")


async def telemetry_ticker(backend, executor, plan: MissionPlan, every_s: float) -> None:
    """Live flight readout — the demo's stand-in for the M3 dashboard."""
    try:
        while True:
            tel = await backend.latest_telemetry()
            if tel is not None:
                state = executor.machine.current_state.id
                d_home = distance_m(tel.position, plan.property.home)
                print(
                    f"  [tel] state={state:<10} alt={tel.alt_rel_m:6.1f} m  "
                    f"dist_home={d_home:6.1f} m  batt={tel.battery_pct:5.1f}%  "
                    f"mode={tel.flight_mode:<12} photos={len(executor.media)}"
                )
            await asyncio.sleep(every_s)
    except asyncio.CancelledError:
        return


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


async def main() -> int:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="D7: natural language -> governed simulated flight")
    ap.add_argument("request", nargs="*", help="the operator's natural-language request")
    ap.add_argument("--backend", choices=["fake", "px4"], default="fake")
    ap.add_argument("--model", default=None,
                    help='PydanticAI model id, or "scripted" for the keyless demo model')
    ap.add_argument("--auto-approve", action="store_true",
                    help="skip the interactive approval prompt (demo/CI)")
    ap.add_argument("--operator", default=None, help="name recorded on the approval")
    ap.add_argument("--db", default="runs/mission_events.sqlite3",
                    help="event-log SQLite path (audit trail)")
    ap.add_argument("--time-scale", type=float, default=0.05,
                    help="fake backend only: motion time scale (0 = instant)")
    ap.add_argument("--tick", type=float, default=2.0, help="telemetry printout period, seconds")
    ap.add_argument("--connect-timeout", type=float, default=60.0)
    args = ap.parse_args()

    request_text = " ".join(args.request) or DEFAULT_REQUEST
    operator = args.operator or os.environ.get("USER") or getpass.getuser() or "operator"

    # ---- 0. the aircraft ---------------------------------------------------- #
    backend = await make_backend(args.backend, args.time_scale, args.connect_timeout)
    tel = await first_telemetry(backend)
    prop = property_around(tel.position)
    print(f"backend: {backend.name}   home: ({tel.position.lat:.6f},{tel.position.lon:.6f})   "
          f"battery: {tel.battery_pct:.0f}%")

    # ---- 1. natural language -> validated plan (planner + static rules) ----- #
    model = pick_model(args.model)
    if model is None:
        print("\nNo model available. Set ANTHROPIC_API_KEY or OPENAI_API_KEY (or put it in "
              "drone-mission/.env), pass --model <id>, or use --model scripted for the "
              "keyless demo.")
        await backend.disconnect()
        return 2
    model_obj = scripted_model(prop) if model == "scripted" else model

    mission_id = f"D7-{time.strftime('%Y%m%d-%H%M%S')}"
    print(f"\nmodel: {model}\nmission: {mission_id}\nrequest: {request_text}")

    planner = MissionPlanner(model_obj)
    result = await planner.plan(
        PlanRequest(
            mission_id=mission_id,
            request_text=request_text,
            property=prop,
            limits=Limits(),
            failsafe=FailsafePolicy(),
        )
    )
    print(f"planner rounds: {result.rounds}")
    if result.plan is None or result.report is None or not result.report.ok:
        if result.report is not None:
            print_report(result.report, title="STATIC VALIDATION (planner could not satisfy)")
        print("\nThe planner never produced a rule-clean plan. Nothing will fly. (exit 2)")
        await backend.disconnect()
        return 2
    plan = result.plan
    print_plan(plan)
    print_report(result.report, title="STATIC VALIDATION (Waves 1-3): PASS")

    # ---- 2. LIVE validation: the plan against the actual drone, now --------- #
    # Telemetry FIRST, clock second (same order as the executor's _live_ctx):
    # sampling the clock before the snapshot makes telemetry look like it is
    # from the future, and Wave 4 rightly refuses to reason from clock skew.
    live_tel = await backend.latest_telemetry()
    live_ctx = ValidationContext(
        now_ts=time.time(),
        telemetry=live_tel,
        capabilities=backend.capabilities(),
    )
    live_report = validate_plan(plan, live_ctx)
    print_report(live_report, title="LIVE VALIDATION (Wave 4: telemetry + capabilities)")
    if not live_report.ok:
        print("\nLive validation refused this plan against the current drone state. (exit 3)")
        await backend.disconnect()
        return 3

    # ---- 3. the human ------------------------------------------------------- #
    est_min = estimate_mission_duration_s(plan) / 60.0
    plan_hash = compute_plan_hash(plan)
    print("\n=== APPROVAL GATE ===")
    print(f"  mission:         {plan.mission_id}")
    print(f"  expected photos: {plan.expected_capture_count()}")
    print(f"  estimated time:  {est_min:.1f} min (conservative)")
    print(f"  plan hash:       {plan_hash[:16]}…  (approval binds to THIS exact plan)")
    if args.auto_approve:
        print(f"  --auto-approve: approving as '{operator}' (demo mode)")
    else:
        # to_thread keeps the event loop alive while the human thinks —
        # a blocking input() would freeze the PX4 telemetry cache streams.
        answer = await asyncio.to_thread(
            input, "  Type APPROVE to authorize this SIMULATED flight (anything else denies): "
        )
        if answer.strip() != "APPROVE":
            print("  Denied by operator. Nothing flies. (exit 4)")
            await backend.disconnect()
            return 4
    try:
        approval = grant_approval(
            plan, live_report, operator=operator, now_ts=time.time(), profile="sim"
        )
    except ApprovalError as exc:
        print(f"  APPROVAL REFUSED: {exc} (exit 3)")
        await backend.disconnect()
        return 3
    print(f"  approval {approval.approval_id} granted to '{operator}' (profile=sim, TTL 300 s)")

    # ---- 4. flight ----------------------------------------------------------- #
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    log = EventLog(args.db)
    executor = MissionExecutor(
        plan, approval, backend, log, clock=time.time, profile="sim"
    )

    loop = asyncio.get_running_loop()

    def _on_sigint() -> None:
        print("\n>>> ABORT requested: preempting current command, flying RTH + land. "
              "(Ctrl+C again = hard kill)")
        executor.abort()
        try:
            loop.remove_signal_handler(signal.SIGINT)
        except (ValueError, NotImplementedError):
            pass

    try:
        loop.add_signal_handler(signal.SIGINT, _on_sigint)
    except NotImplementedError:  # non-unix; fall back to default KeyboardInterrupt
        pass

    print(f"\n=== EXECUTING (Ctrl+C = operator abort -> RTH + land) — audit log: {args.db} ===")
    ticker = asyncio.ensure_future(telemetry_ticker(backend, executor, plan, args.tick))
    try:
        mission = await executor.run()
    finally:
        ticker.cancel()
        try:
            loop.remove_signal_handler(signal.SIGINT)
        except (ValueError, NotImplementedError):
            pass

    # ---- 5. the story the system can prove ----------------------------------- #
    print("\n=== RESULT ===")
    print(f"  outcome:         {mission.outcome.value}")
    print(f"  final state:     {mission.final_state}")
    if mission.reason:
        print(f"  reason:          {mission.reason}")
    print(f"  steps completed: {mission.steps_completed}/{len(plan.steps)}")
    print(f"  photos:          {len(mission.media)}")
    for ref in mission.media:
        where = ref.path or f"media_id={ref.media_id}"
        print(f"    - {ref.tag:<20} {where}")

    events = log.replay(plan.mission_id)
    print(f"\n=== AUDIT TRAIL ({len(events)} events, append-only, {args.db}) ===")
    for e in events:
        keys = {k: v for k, v in e.payload.items() if k in
                ("event", "source", "target", "step", "action", "attempt", "rules",
                 "reason", "ok", "tag", "distance_m", "alt_m", "command", "where")}
        detail = " ".join(f"{k}={v}" for k, v in keys.items())
        print(f"  {e.seq:3d}  {e.type:<20} {detail[:88]}")

    log.close()
    await backend.disconnect()
    if mission.outcome is MissionOutcome.COMPLETED:
        print("\nD7 COMPLETE — the sentence became a governed, audited, simulated flight.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
