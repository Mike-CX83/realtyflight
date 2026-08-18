"""D12.1 server hardening regression tests — the 2026-08-17 review-rerun
findings on the dashboard side:

- server shutdown must never orphan a flying mission: the lifespan hook
  requests abort, waits boundedly, then disconnects the backend
- EVERY failed planning path (including a 500 before the planner even runs)
  clears the pending plan — no stale approvals, ever
- operator identities refuse control/format characters, not just whitespace
"""

from __future__ import annotations

import pytest

from tests.test_server import auth, dash, wait_state
from tests.test_server_d12 import _approve_body, _plan


def test_server_shutdown_aborts_active_mission_and_disconnects(tmp_path):
    """Rerun: 'the server has no lifespan cleanup to abort an active mission
    and disconnect PX4 before shutdown.' Now it does — exiting the server with
    a mission mid-flight aborts it (bounded) and disconnects the backend."""
    with dash(tmp_path, hooks={("goto", 0): "hang"}) as (client, backend):
        p = _plan(client)
        r = client.post("/api/approve", headers=auth(), json=_approve_body(p))
        assert r.status_code == 200
        wait_state(client, lambda s: s["mission_active"])
        # leave the with-block with the mission STILL FLYING (goto hung)

    assert backend.connected is False, "backend never disconnected on shutdown"
    assert backend.abort_motion_calls >= 1, "shutdown never aborted the mission"
    assert backend.in_air is False, "shutdown abort never recovered the aircraft"


def test_plan_crash_before_planner_still_clears_pending(tmp_path, monkeypatch):
    """Rerun: failures BEFORE the planner branch (missing telemetry, dead
    helper, cancellation) left the previous pending plan approvable. Pending
    is now invalidated at the START of every planning attempt."""
    with dash(tmp_path) as (client, backend):
        first = _plan(client)

        def boom(*a, **k):
            raise RuntimeError("helper exploded before the planner ran")

        monkeypatch.setattr("server.app.property_around", boom)
        with pytest.raises(RuntimeError):
            client.post(
                "/api/plan", headers=auth(),
                json={"request_text": "again", "operator": "mike"},
            )

        r = client.post("/api/approve", headers=auth(), json=_approve_body(first))
        assert r.status_code == 409, "stale pending plan survived a crashed re-plan"


def test_control_character_operator_is_rejected(tmp_path):
    with dash(tmp_path) as (client, backend):
        r = client.post(
            "/api/plan", headers=auth(),
            json={"request_text": "x", "operator": "mi\x07ke"},
        )
        assert r.status_code == 422
