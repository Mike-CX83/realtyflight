"""D12.3 server hardening regression tests — review #3, dashboard side:

- invisible-Unicode operator identities (zero-width space, bidi override,
  C1 controls) are rejected, not just ASCII C0 controls
- /api/state never mixes a NEW pending plan's identity with the OLD
  executor's progress: mission fields describe THE MISSION (the executor);
  the plan card gets its data from /api/plan's own response
"""

from __future__ import annotations

from tests.test_server import auth, dash, wait_state
from tests.test_server_d12 import _approve_body, _plan


def test_invisible_unicode_operators_are_rejected(tmp_path):
    with dash(tmp_path) as (client, backend):
        for evil in ("\u200b", "mi\u202eke", "mi\u0085ke"):
            r = client.post(
                "/api/plan", headers=auth(),
                json={"request_text": "x", "operator": evil},
            )
            assert r.status_code == 422, f"accepted invisible operator {evil!r}"


def test_state_never_mixes_pending_plan_with_old_mission(tmp_path):
    with dash(tmp_path) as (client, backend):
        p1 = _plan(client)
        r = client.post("/api/approve", headers=auth(), json=_approve_body(p1))
        assert r.status_code == 200
        wait_state(client, lambda s: s["outcome"] == "completed")

        p2 = _plan(client)                              # new pending, old executor
        s = client.get("/api/state", headers=auth()).json()
        assert s["mission_id"] == p1["mission_id"], (
            "state reported the pending plan's ID with the old mission's data"
        )
        assert s["outcome"] == "completed"
        assert p2["mission_id"] != p1["mission_id"]
