"""D12 server hardening regression tests — the dashboard side of the
2026-08-16 external review findings:

- strict Bearer parsing (a bare secret in the Authorization header is a 401)
- operator names are stripped + nonblank everywhere (no whitespace identities)
- APPROVE pins the reviewed plan: the page submits mission_id + plan_hash and
  a swapped pending plan is a 409, never a silent approval of the unseen plan
- a planner failure is a clean ok:false (never a 500) and CLEARS the pending
  plan — no stale approvals of an earlier proposal
- mission IDs are collision-resistant (two plans in the same second differ)
- the governance chain is IN the event log: plan.proposed + approval.granted
  (with operator + plan hash) appear in the mission's replay
- tripping the breaker over HTTP preempts the active mission NOW (freeze-only:
  no RTL/land afterward), instead of merely latching a flag
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from backends.fake import FakeBackend, FakeConfig
from server.app import create_app
from tests.test_server import SECRET, auth, dash, wait_state


def _plan(client, text="Photograph this property: full exterior package."):
    r = client.post(
        "/api/plan", headers=auth(), json={"request_text": text, "operator": "mike"}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _approve_body(plan_resp: dict) -> dict:
    return {
        "operator": "mike",
        "mission_id": plan_resp["mission_id"],
        "plan_hash": plan_resp["plan_hash"],
    }


# --------------------------------------------------------------------------- #
# Auth strictness
# --------------------------------------------------------------------------- #


def test_bare_token_without_bearer_scheme_is_rejected(tmp_path):
    with dash(tmp_path) as (client, backend):
        r = client.post(
            "/api/plan",
            headers={"Authorization": SECRET},          # correct secret, no scheme
            json={"request_text": "x", "operator": "mike"},
        )
        assert r.status_code == 401


def test_whitespace_operator_is_rejected(tmp_path):
    with dash(tmp_path) as (client, backend):
        r = client.post(
            "/api/plan", headers=auth(),
            json={"request_text": "x", "operator": "   "},
        )
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Approval pins the REVIEWED plan
# --------------------------------------------------------------------------- #


def test_approve_pins_the_reviewed_plan(tmp_path):
    """Plan A is on the operator's screen; plan B lands behind their back.
    Approving with A's mission_id+hash must be a 409 — the review's
    concurrent-swap scenario. Approving what is actually pending works."""
    with dash(tmp_path) as (client, backend):
        first = _plan(client)
        second = _plan(client, text="Photograph this property: orbit only.")
        assert first["mission_id"] != second["mission_id"]

        r = client.post("/api/approve", headers=auth(), json=_approve_body(first))
        assert r.status_code == 409, "approved a plan the operator never reviewed"

        r = client.post("/api/approve", headers=auth(), json=_approve_body(second))
        assert r.status_code == 200, r.text
        wait_state(client, lambda s: s["outcome"] == "completed")


def test_planner_crash_is_a_clean_failure_not_a_500(tmp_path):
    backend = FakeBackend(clock=time.time, config=FakeConfig())
    app = create_app(
        backend=backend, model=object(),                 # not a real model: planner dies
        secret=SECRET, log_path=str(tmp_path / "events.sqlite3"),
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/plan", headers=auth(),
            json={"request_text": "x", "operator": "mike"},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is False


def test_failed_plan_clears_pending(tmp_path, monkeypatch):
    """A good plan is pending; the next planning attempt fails. The stale
    pending plan must be GONE — approving it afterward is a 409."""
    with dash(tmp_path) as (client, backend):
        first = _plan(client)

        class DeadPlanner:
            def __init__(self, *a, **k):
                pass

            async def plan(self, req):
                raise RuntimeError("LLM API down")

        monkeypatch.setattr("server.app.MissionPlanner", DeadPlanner)
        r = client.post(
            "/api/plan", headers=auth(),
            json={"request_text": "again", "operator": "mike"},
        )
        assert r.status_code == 200 and r.json()["ok"] is False

        r = client.post("/api/approve", headers=auth(), json=_approve_body(first))
        assert r.status_code == 409, "stale pending plan survived a failed re-plan"


def test_mission_ids_are_collision_resistant(tmp_path):
    with dash(tmp_path) as (client, backend):
        a = _plan(client)["mission_id"]
        b = _plan(client)["mission_id"]                  # same wall-clock second
        assert a != b


# --------------------------------------------------------------------------- #
# The governance chain is in the audit log
# --------------------------------------------------------------------------- #


def test_replay_contains_full_governance_chain(tmp_path):
    with dash(tmp_path) as (client, backend):
        p = _plan(client)
        r = client.post("/api/approve", headers=auth(), json=_approve_body(p))
        assert r.status_code == 200
        wait_state(client, lambda s: s["outcome"] == "completed")

        events = client.get(
            f"/api/replay/{p['mission_id']}", headers=auth()
        ).json()["events"]
        by_type = {e["type"]: e for e in events}
        assert "plan.proposed" in by_type, "planning must be in the audit trail"
        assert "approval.granted" in by_type
        granted = by_type["approval.granted"]["payload"]
        assert granted["operator"] == "mike"
        assert granted["plan_hash"].startswith(p["plan_hash"])


# --------------------------------------------------------------------------- #
# The HTTP kill switch preempts NOW (freeze-only)
# --------------------------------------------------------------------------- #


def test_breaker_trip_preempts_active_mission_over_http(tmp_path):
    with dash(tmp_path, hooks={("goto", 1): "hang"}) as (client, backend):
        p = _plan(client)
        r = client.post("/api/approve", headers=auth(), json=_approve_body(p))
        assert r.status_code == 200
        wait_state(client, lambda s: s["mission_state"] == "executing")

        cut = len(backend.command_log)
        r = client.post(
            "/api/breaker", headers=auth(),
            json={"operator": "mike", "action": "trip", "reason": "phone kill tap"},
        )
        assert r.json()["breaker_open"] is True

        s = wait_state(client, lambda s: s["outcome"] == "failed", timeout_s=4.0)
        assert "breaker" in s["reason"].lower()
        after = [a for a, _ in backend.command_log[cut:]]
        assert "return_home" not in after and "land" not in after   # freeze-only
        assert backend.abort_motion_calls >= 1
