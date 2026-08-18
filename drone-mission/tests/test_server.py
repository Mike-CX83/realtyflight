"""D11 dashboard server tests — the governance flow over HTTP, on the fake
backend with the scripted model. The rules under test:

- no anonymous anything: every flight-affecting route 401s without the token
- the full flow works: plan -> checklist -> approve -> mission completes ->
  photos + state + replay all visible through the API
- a tripped breaker means an approved mission still never dispatches
- abort over HTTP preempts a flying mission

Harness note: TestClient must be used as a context manager — that keeps ONE
event loop alive for the client's lifetime (like uvicorn does), so the mission
task created during /api/approve keeps running between requests. Without it,
each request gets a throwaway loop and the mission task is cancelled the
moment approve returns (we discovered this the fun way).
"""

from __future__ import annotations

import time
from contextlib import contextmanager

from fastapi.testclient import TestClient

from backends.fake import FakeBackend, FakeConfig
from server.app import create_app

SECRET = "test-secret-token"


@contextmanager
def dash(tmp_path, *, hooks: dict | None = None):
    backend = FakeBackend(clock=time.time, config=FakeConfig())
    if hooks:
        backend.hooks.update(hooks)
    app = create_app(
        backend=backend, model="scripted", secret=SECRET,
        log_path=str(tmp_path / "events.sqlite3"),
    )
    with TestClient(app) as client:
        yield client, backend


def auth() -> dict:
    return {"Authorization": f"Bearer {SECRET}"}


def wait_state(client, pred, timeout_s: float = 10.0) -> dict:
    deadline = time.time() + timeout_s
    s: dict = {}
    while time.time() < deadline:
        s = client.get("/api/state", headers=auth()).json()
        if pred(s):
            return s
        time.sleep(0.05)
    raise AssertionError(f"state condition not reached in {timeout_s}s; last: {s}")


# --------------------------------------------------------------------------- #
# Auth stub: real bones
# --------------------------------------------------------------------------- #


def test_every_mutating_route_requires_the_token(tmp_path):
    with dash(tmp_path) as (client, _):
        assert client.post("/api/plan",
                           json={"request_text": "x", "operator": "m"}).status_code == 401
        assert client.post(
            "/api/approve",
            json={"operator": "m", "mission_id": "X", "plan_hash": "0" * 16},
        ).status_code == 401
        assert client.post("/api/abort", json={"operator": "m"}).status_code == 401
        assert client.post("/api/breaker",
                           json={"operator": "m", "action": "trip"}).status_code == 401
        assert client.get("/api/state").status_code == 401
        bad = {"Authorization": "Bearer nope"}
        assert client.get("/api/state", headers=bad).status_code == 401


def test_operator_name_is_required_on_approval(tmp_path):
    with dash(tmp_path) as (client, _):
        r = client.post(
            "/api/approve",
            json={"operator": "", "mission_id": "X", "plan_hash": "0" * 16},
            headers=auth(),
        )
        assert r.status_code == 422  # pydantic body validation: no anonymous approve


# --------------------------------------------------------------------------- #
# The full governed flow over HTTP
# --------------------------------------------------------------------------- #


def test_plan_approve_fly_replay_full_flow(tmp_path):
    with dash(tmp_path) as (client, backend):
        # 1) plan
        r = client.post("/api/plan", headers=auth(),
                        json={"request_text": "full exterior package", "operator": "mike"})
        assert r.status_code == 200
        p = r.json()
        assert p["ok"] is True
        assert p["expected_photos"] == 11
        assert any(row["rule"] == "GEO-03" and row["passed"] for row in p["report"])
        assert len(p["boundary"]) >= 3 and p["plan_hash"]
        mission_id = p["mission_id"]

        # 2) approve -> mission starts (D12: approving THIS reviewed plan)
        r = client.post(
            "/api/approve",
            json={"operator": "mike", "mission_id": p["mission_id"],
                  "plan_hash": p["plan_hash"]},
            headers=auth(),
        )
        assert r.status_code == 200
        assert r.json()["approved"] is True and r.json()["operator"] == "mike"

        # 3) mission runs to completion
        s = wait_state(client, lambda s: s["outcome"])
        assert s["outcome"] == "completed"
        assert s["photos"] == 11
        assert s["mission_state"] == "completed"
        assert backend.in_air is False

        # 4) replay: the audit trail is served
        r = client.get(f"/api/replay/{mission_id}", headers=auth())
        assert r.status_code == 200
        types = [e["type"] for e in r.json()["events"]]
        assert "approval.activated" in types and "mission.closed" in types
        assert types.count("media.captured") == 11

        # 5) mission listing includes it
        r = client.get("/api/missions", headers=auth())
        assert any(m["mission_id"] == mission_id for m in r.json()["missions"])


def test_approve_without_plan_conflicts(tmp_path):
    with dash(tmp_path) as (client, _):
        r = client.post(
            "/api/approve",
            json={"operator": "mike", "mission_id": "X", "plan_hash": "0" * 16},
            headers=auth(),
        )
        assert r.status_code == 409


def test_breaker_trip_means_an_approved_mission_never_dispatches(tmp_path):
    with dash(tmp_path) as (client, backend):
        r = client.post("/api/plan", headers=auth(),
                        json={"request_text": "package", "operator": "mike"})
        p = r.json()
        assert p["ok"] is True

        r = client.post("/api/breaker", headers=auth(),
                        json={"operator": "mike", "action": "trip", "reason": "range officer"})
        assert r.json()["breaker_open"] is True

        r = client.post(
            "/api/approve",
            json={"operator": "mike", "mission_id": p["mission_id"],
                  "plan_hash": p["plan_hash"]},
            headers=auth(),
        )
        assert r.status_code == 200  # approval granted...

        s = wait_state(client, lambda s: s["outcome"])
        assert s["outcome"] == "rejected_at_gate"    # ...but the gate said no
        assert backend.command_log == []             # nothing was ever sent

        r = client.post("/api/breaker", headers=auth(),
                        json={"operator": "mike", "action": "reset"})
        assert r.json()["breaker_open"] is False


def test_abort_over_http_preempts_a_flying_mission(tmp_path):
    with dash(tmp_path, hooks={("goto", 0): "hang"}) as (client, backend):
        r = client.post("/api/plan", headers=auth(),
                        json={"request_text": "package", "operator": "mike"})
        p = r.json()
        client.post(
            "/api/approve",
            json={"operator": "mike", "mission_id": p["mission_id"],
                  "plan_hash": p["plan_hash"]},
            headers=auth(),
        )

        # airborne with the goto hung
        wait_state(client, lambda s: s["mission_active"] and s["steps_completed"] >= 1)

        r = client.post("/api/abort", json={"operator": "mike"}, headers=auth())
        assert r.status_code == 200

        s = wait_state(client, lambda s: s["outcome"])
        assert s["outcome"] in ("aborted", "failed")
        assert backend.in_air is False               # recovery flew it home
        assert backend.abort_motion_calls >= 1


def test_dashboard_page_is_served(tmp_path):
    with dash(tmp_path) as (client, _):
        r = client.get("/")
        assert r.status_code == 200
        assert "RealtyFlight" in r.text and "APPROVE" in r.text
