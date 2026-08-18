# D12.1 Handoff — the review RERUN absorbed (round 2.1)

You are the Claude agent in Mike's IDE. Read `CLAUDE.md` first. This builds on
the D12 commit you already made. Simulation only; plain `gz_x500`.

## What happened

The external reviewer RERAN against the D12 tree: verdict 6/10 invariants
verified (was 3/10), four still broken. The Cowork session verified the rerun's
claims (line numbers matched exactly again — all the Criticals are real) and
built D12.1. Note: the rerun's "collection failed / missing fastapi" is the
REVIEWER'S OWN venv (it used a repo-local `.venv`, not `~/.venvs/drone-mission`)
— if a stray `drone-mission/.venv` exists, either `pip install -e ".[dev]"`
into it or remove it, your call.

## What D12.1 fixes (all regression-test-first: 13 new tests, 9 proven
failing on the D12 code)

- **The FULL live gate now runs before EVERY work command** (rerun C1): orbit
  waypoints, captures, retries re-check battery/GPS/freshness/capabilities/
  approval/profile via `_live_guard()`, plus manual-stick detection. The
  rerun's probe (battery to 0% mid-orbit → 44 more commands) now stops at the
  very next command and failsafes home. Plan-tail RTL/land still bypass
  reality gates BY DESIGN (flying home on a dead battery must never be vetoed
  by the battery rule) — they check abort/breaker only.
- **Approval TTL can't be laundered by a slow preflight** (rerun C2): the gate
  re-runs at "activation", after preflight, immediately before the first
  dispatch.
- **Kill preempts RECOVERY too** (rerun C3): recovery RTL/land run in the same
  preemptible task slot, and the breaker is re-checked before EACH recovery
  command — a kill mid-recovery freezes; land never crosses an open breaker.
  `_wait_resume` wakes on kill (a kill while paused froze forever before).
  `abort_motion` is bounded (`_freeze()`), and PX4 records its failures.
- **HOLD is now PREEMPTIVE**: `hold()` cancels the in-flight step; the drone
  freezes and pauses NOW; resume re-dispatches the SAME step on the same
  idempotency key (that's what the keys are for — PX4's in-flight registry
  reconciles instead of re-sending). Hold during return/land phases is
  recorded `hold.ignored` by design.
- **Speed hard cap always on** (rerun C5): observed speed is monitored even
  when the speed ACK "succeeds"; cap = requested + max(1 m/s, 15%) with a
  3-consecutive-poll debounce. The rerun's probe (5.4 m/s on a 4 m/s
  approval) now dies at 5.0.
- **Freshness is a band** (rerun C6): 0 ≤ age ≤ limit in `_fresh_tel` and
  `_landed_evidence` — future-dated telemetry proves nothing (matches Wave-4).
- **Gimbal joins the in-flight idempotency registry** (rerun C4); capture
  stays re-execute-on-retry BY DESIGN (same key → same media_id/paths →
  overwrite; skipping could mark done with no file).
- **ABORTED never leaves the machine nonterminal** (returning → landing →
  touchdown settle); `mission.closed` now records outcome + reason.
- **Server**: lifespan shutdown aborts an active mission (bounded 15 s) and
  disconnects the backend; EVERY failed/crashed plan attempt clears pending
  state (server AND browser); operators refuse control characters; audit-write
  drops are counted and surfaced in `/api/state` (`audit_drops`).
- **Watchdog budgets** derive from the mission envelope (worst legal leg,
  altitude, capture counts) instead of flat 30 s/15 s constants.
- README refreshed (230 tests, dashboard shipped, D12/D12.1 rows).

Changed files (on disk, uncommitted): `core/engine/executor.py`,
`backends/px4_mavsdk/backend.py`, `server/app.py`, `server/static/index.html`,
`README.md` (drone-mission), NEW `tests/test_hardening_d121.py`,
NEW `tests/test_server_d121.py`.

Verified in the cloud: **suite 230 passed, 6 skipped**, ruff clean, live HTTP
run: plan → approve → mid-flight HOLD reached `paused` promptly → resume →
completed 11/11 photos, audit_drops 0.

## Do, in order

1. `cd drone-mission && source ~/.venvs/drone-mission/bin/activate`
2. `pytest -q` → **230 passed, 6 skipped**; `ruff check .` → clean.
3. SITL re-cert (adapter changed AGAIN — required):
   `docker rm -f px4sitl 2>/dev/null; docker run -d -t --rm --name px4sitl jonasvautherin/px4-gazebo-headless:1.17.0`
   → `RUN_PX4_CONTRACT=1 pytest tests/test_backend_contract.py -q` → 12 passed
   → `python -m backends.px4_mavsdk.smoke` → SMOKE FLIGHT COMPLETE.
   **Watch specifically for false overspeed trips** (the always-on hard cap is
   the one change with live-flight risk): if a goto dies with "sustained ...
   over the approved", record the observed speeds — the margin may need a
   bump for SITL; report before changing anything.
4. Live dashboard drill against PX4:
   `DASH_BACKEND=px4 DASH_SECRET=$(openssl rand -hex 8) python -m server`
   — plan/approve via curl (approve body needs mission_id + plan_hash), then
   mid-flight: POST /api/hold → verify state `paused` and the drone holds in
   QGC; /api/resume → completes. On a second mission, the kill drill as in
   D12 (freeze, no RTL). Ctrl-C the server WHILE a third mission flies —
   verify the shutdown path aborts + recovers it (watch QGC) and the process
   exits cleanly.
5. Bookkeeping:
   - TODO: D12.1 entry [x] under D12 with the rerun verdict (6/10 → the four
     broken invariants closed) + 230/6. Add a **"Deferred with reasons"**
     note (these are DECISIONS, not omissions — record them):
     (a) in-core report forgery → real fix is an approval service boundary;
     G5/real-flight work (an attacker constructing Python objects in-process
     already owns the process; hash+manifest binding covers accidental misuse);
     (b) failsafe-policy field mapping (gps_hold_timeout_s, on_link_loss,
     telemetry_stale_failsafe_s) → its own milestone, candidate next hardening;
     (c) audit async writer + hash-chain/immutability enforcement → with (b);
     (d) manual-input population from RC status + is_physical explicit
     composition → A-track (first real aircraft);
     (e) python-statemachine `configuration` migration → existing chore;
     (f) sat_count stays ADVISORY when present (fresh gps_ok is the
     load-bearing deny) — documented decision, test-pinned.
   - JOURNAL chapter: rerun verdict, the preemptive-hold doctrine, deferrals.
   - `rm D12_1_HANDOFF.md`, `git add -A`, commit:
     `D12.1: review rerun absorbed — full gate per command, preemptive hold, recovery preemption, approval TTL, speed hard cap (230 tests)`
     push, confirm CI green.

## Hard rules
- The 13 new tests pin the rerun's findings — never weaken one to pass. Live
  PX4 disagreement: adapter first, margins second (report first), tests last.
- 3-strikes; JOURNAL everything.

## Report
Suite count, contract 12/12, smoke, HOLD drill (did it pause mid-flight?),
kill drill, shutdown drill, any overspeed false-trips with numbers, CI status.
