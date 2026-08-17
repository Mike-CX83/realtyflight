"""The D11 dashboard server: FastAPI routes over the governed mission engine.

Design rules (TODO D11; docs 14 §4):
- AUTH STUB WITH REAL BONES: every flight-affecting route sits behind one
  dependency (`require_token`) checking a shared secret, and every such action
  carries a named operator — there is no anonymous APPROVE, even in sim. The
  dependency is the designed swap-point for real accounts + TLS before anything
  physical or internet-reachable (CLAUDE.md security rule).
- No engine logic here. Routes translate HTTP/WS to the SAME planner,
  validator, approval, executor, and event log the terminal demo uses.
- Backend-agnostic: the app is built around any DroneBackend (fake for tests
  and dev, PX4 SITL for the real demo) — injected via create_app for tests.

Run:  python -m server            (env: DASH_BACKEND=fake|px4, DASH_MODEL,
                                   DASH_SECRET, DASH_PORT — see __main__.py)
"""

from __future__ import annotations

import asyncio
import hmac
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from core.approval import ApprovalError, ApprovalRecord, grant_approval
from core.engine import MissionExecutor
from core.events import EventLog
from core.geo import distance_m
from core.policy.dispatch import CircuitBreaker
from core.policy.engine import validate_plan
from core.policy.rules_wave4 import ValidationContext, estimate_mission_duration_s
from core.schema import FailsafePolicy, Limits, MissionPlan, compute_plan_hash
from demo.fly import pick_model, property_around, scripted_model
from planner import MissionPlanner, PlanRequest

STATIC_DIR = Path(__file__).resolve().parent / "static"


# --------------------------------------------------------------------------- #
# Request/response bodies
# --------------------------------------------------------------------------- #


class PlanBody(BaseModel):
    request_text: str = Field(min_length=1, max_length=2000)
    operator: str = Field(min_length=1, max_length=120)


class OperatorBody(BaseModel):
    operator: str = Field(min_length=1, max_length=120)


class BreakerBody(BaseModel):
    operator: str = Field(min_length=1, max_length=120)
    action: str = Field(pattern="^(trip|reset)$")
    reason: str = Field(default="operator kill switch", max_length=300)


# --------------------------------------------------------------------------- #
# App state
# --------------------------------------------------------------------------- #


@dataclass
class Session:
    """One dashboard session: one backend, one mission at a time."""

    backend: object
    model: object                      # PydanticAI model id/instance, or "scripted"
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    log_path: str = "runs/mission_events.sqlite3"

    pending_plan: MissionPlan | None = None
    pending_report: object | None = None      # live-checked ValidationReport
    approval: ApprovalRecord | None = None
    executor: MissionExecutor | None = None
    mission_task: asyncio.Task | None = None
    result: object | None = None              # MissionResult once terminal
    planner_rounds: int = 0

    def mission_active(self) -> bool:
        return self.mission_task is not None and not self.mission_task.done()


def _report_rows(report) -> list[dict]:
    return [
        {
            "rule": r.rule,
            "description": r.description,
            "passed": r.passed,
            "violations": [v.message for v in r.violations],
        }
        for r in report.results
    ]


def _steps_json(plan: MissionPlan) -> list[dict]:
    return [s.model_dump(mode="json", exclude_none=True) for s in plan.steps]


# --------------------------------------------------------------------------- #
# App factory
# --------------------------------------------------------------------------- #


def create_app(
    *,
    backend,
    model=None,
    secret: str | None = None,
    log_path: str = "runs/mission_events.sqlite3",
) -> FastAPI:
    """Build the dashboard app around an already-connected DroneBackend."""

    token = secret or secrets.token_urlsafe(24)
    sess = Session(backend=backend, model=model, log_path=log_path)
    app = FastAPI(title="RealtyFlight dashboard", docs_url=None, redoc_url=None)
    app.state.token = token  # __main__ prints it at startup

    # ---- the auth stub (swap-point for real accounts + TLS later) ---------- #
    async def require_token(authorization: str = Header(default="")) -> None:
        supplied = authorization.removeprefix("Bearer ").strip()
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(status_code=401, detail="missing or bad token")

    # ---- helpers ------------------------------------------------------------ #
    async def live_ctx() -> ValidationContext:
        tel = await sess.backend.latest_telemetry()  # telemetry FIRST,
        return ValidationContext(                    # clock second (D7 lesson)
            now_ts=time.time(), telemetry=tel, capabilities=sess.backend.capabilities()
        )

    async def state_snapshot() -> dict:
        tel = await sess.backend.latest_telemetry()
        ex = sess.executor
        plan = sess.pending_plan or (ex.plan if ex else None)
        home = plan.property.home if plan else None
        return {
            "ts": time.time(),
            "backend": getattr(sess.backend, "name", "unknown"),
            "breaker_open": sess.breaker.is_open,
            "mission_active": sess.mission_active(),
            "mission_state": ex.machine.current_state.id if ex else None,
            "mission_id": plan.mission_id if plan else None,
            "steps_total": len(plan.steps) if plan else 0,
            "steps_completed": ex._steps_completed if ex else 0,
            "photos": len(ex.media) if ex else 0,
            "media": [
                {"tag": m.tag, "media_id": m.media_id, "path": m.path}
                for m in (ex.media if ex else [])
            ],
            "outcome": (sess.result.outcome.value if sess.result else None),
            "reason": (sess.result.reason if sess.result else ""),
            "telemetry": (
                {
                    "lat": tel.position.lat,
                    "lon": tel.position.lon,
                    "alt_rel_m": round(tel.alt_rel_m, 1),
                    "battery_pct": round(tel.battery_pct, 1),
                    "speed_ms": round(tel.speed_ms, 1),
                    "in_air": tel.in_air,
                    "flight_mode": tel.flight_mode,
                    "dist_home_m": round(distance_m(tel.position, home), 1) if home else None,
                }
                if tel
                else None
            ),
        }

    # ---- pages -------------------------------------------------------------- #
    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse((STATIC_DIR / "index.html").read_text())

    @app.get("/media/{name}")
    async def media(name: str, t: str = "", authorization: str = Header(default="")):
        # <img> tags can't send headers — accept the token as ?t= as well.
        supplied = (authorization.removeprefix("Bearer ").strip()) or t
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(status_code=401, detail="missing or bad token")
        # sanitized: serve only plain filenames out of the backend's media dir
        if "/" in name or "\\" in name or name.startswith("."):
            raise HTTPException(400, "bad name")
        media_dir = Path(getattr(getattr(sess.backend, "cfg", None), "media_dir", "media"))
        f = media_dir / name
        if not f.is_file():
            raise HTTPException(404, "no such media")
        return FileResponse(f)

    # ---- the governed flow -------------------------------------------------- #
    @app.post("/api/plan")
    async def plan(body: PlanBody, _=Depends(require_token)):
        if sess.mission_active():
            raise HTTPException(409, "a mission is executing; abort or wait")

        tel = await sess.backend.latest_telemetry()
        if tel is None:
            raise HTTPException(503, "no telemetry from backend yet")
        prop = property_around(tel.position)

        model = sess.model or pick_model(None)
        if model is None:
            raise HTTPException(503, "no LLM configured: set an API key or DASH_MODEL=scripted")
        model_obj = scripted_model(prop) if model == "scripted" else model

        mission_id = f"DASH-{time.strftime('%Y%m%d-%H%M%S')}"
        result = await MissionPlanner(model_obj).plan(
            PlanRequest(
                mission_id=mission_id,
                request_text=body.request_text,
                property=prop,
                limits=Limits(),
                failsafe=FailsafePolicy(),
            )
        )
        if result.plan is None or result.report is None or not result.report.ok:
            return {
                "ok": False,
                "rounds": result.rounds,
                "static_report": _report_rows(result.report) if result.report else [],
                "detail": "planner could not produce a rule-clean plan",
            }

        live_report = validate_plan(result.plan, await live_ctx())
        sess.pending_plan = result.plan
        sess.pending_report = live_report
        sess.result = None
        sess.planner_rounds = result.rounds

        return {
            "ok": live_report.ok,
            "rounds": result.rounds,
            "mission_id": result.plan.mission_id,
            "summary": result.plan.summary,
            "steps": _steps_json(result.plan),
            "report": _report_rows(live_report),
            "expected_photos": result.plan.expected_capture_count(),
            "est_minutes": round(estimate_mission_duration_s(result.plan) / 60.0, 1),
            "plan_hash": compute_plan_hash(result.plan)[:16],
            "boundary": [
                {"lat": p.lat, "lon": p.lon} for p in result.plan.property.boundary
            ],
            "home": {
                "lat": result.plan.property.home.lat,
                "lon": result.plan.property.home.lon,
            },
        }

    @app.post("/api/approve")
    async def approve(body: OperatorBody, _=Depends(require_token)):
        if sess.pending_plan is None or sess.pending_report is None:
            raise HTTPException(409, "nothing awaiting approval — plan first")
        if sess.mission_active():
            raise HTTPException(409, "a mission is already executing")

        # Re-check liveness at the moment of approval, not planning time.
        fresh_report = validate_plan(sess.pending_plan, await live_ctx())
        try:
            approval = grant_approval(
                sess.pending_plan, fresh_report,
                operator=body.operator, now_ts=time.time(), profile="sim",
            )
        except ApprovalError as exc:
            raise HTTPException(409, f"approval refused: {exc}") from exc

        Path(sess.log_path).parent.mkdir(parents=True, exist_ok=True)
        log = EventLog(sess.log_path)
        sess.approval = approval
        sess.executor = MissionExecutor(
            sess.pending_plan, approval, sess.backend, log,
            clock=time.time, profile="sim", breaker=sess.breaker,
        )
        plan_ref = sess.pending_plan
        sess.pending_plan = None
        sess.pending_report = None

        async def fly():
            try:
                sess.result = await sess.executor.run()
            finally:
                log.close()

        sess.mission_task = asyncio.create_task(fly())
        return {
            "approved": True,
            "approval_id": approval.approval_id,
            "operator": approval.operator,
            "mission_id": plan_ref.mission_id,
        }

    @app.post("/api/abort")
    async def abort(body: OperatorBody, _=Depends(require_token)):
        if sess.executor is None or not sess.mission_active():
            raise HTTPException(409, "no active mission")
        sess.executor.rec.record("abort.operator", operator=body.operator)
        sess.executor.abort()
        return {"aborting": True}

    @app.post("/api/hold")
    async def hold(body: OperatorBody, _=Depends(require_token)):
        if sess.executor is None or not sess.mission_active():
            raise HTTPException(409, "no active mission")
        sess.executor.hold()
        return {"holding": True}

    @app.post("/api/resume")
    async def resume(body: OperatorBody, _=Depends(require_token)):
        if sess.executor is None or not sess.mission_active():
            raise HTTPException(409, "no active mission")
        sess.executor.resume()
        return {"resuming": True}

    @app.post("/api/breaker")
    async def breaker(body: BreakerBody, _=Depends(require_token)):
        if body.action == "trip":
            sess.breaker.trip(f"{body.reason} (by {body.operator})")
        else:
            sess.breaker.reset(operator=body.operator)
        return {"breaker_open": sess.breaker.is_open, "reason": sess.breaker.open_reason}

    # ---- read side ----------------------------------------------------------- #
    @app.get("/api/state")
    async def state(_=Depends(require_token)):
        return await state_snapshot()

    @app.get("/api/missions")
    async def missions(_=Depends(require_token)):
        if not await asyncio.to_thread(Path(sess.log_path).exists):
            return {"missions": []}
        log = EventLog(sess.log_path)
        try:
            cur = log._conn.execute(
                "SELECT mission_id, COUNT(*), MIN(ts), MAX(ts) FROM mission_events "
                "GROUP BY mission_id ORDER BY MAX(ts) DESC LIMIT 50"
            )
            rows = [
                {"mission_id": m, "events": n, "started_ts": t0, "ended_ts": t1}
                for (m, n, t0, t1) in cur.fetchall()
            ]
        finally:
            log.close()
        return {"missions": rows}

    @app.get("/api/replay/{mission_id}")
    async def replay(mission_id: str, _=Depends(require_token)):
        if not await asyncio.to_thread(Path(sess.log_path).exists):
            raise HTTPException(404, "no event log yet")
        log = EventLog(sess.log_path)
        try:
            events = log.replay(mission_id)
        finally:
            log.close()
        if not events:
            raise HTTPException(404, "unknown mission id")
        return {
            "mission_id": mission_id,
            "events": [
                {"seq": e.seq, "ts": e.ts, "type": e.type, "payload": e.payload}
                for e in events
            ],
        }

    # ---- live push ------------------------------------------------------------ #
    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        supplied = sock.query_params.get("token", "")
        if not hmac.compare_digest(supplied, token):
            await sock.close(code=4401)
            return
        await sock.accept()
        try:
            while True:
                await sock.send_json(await state_snapshot())
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            return

    return app
