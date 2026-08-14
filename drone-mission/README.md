# drone-mission

The governed mission core for the AI real-estate photography drone capstone.
**Language proposes → rules decide → a human authorizes → a state machine flies.**

Architecture: `../docs/architecture-research/08-target-system-architecture.md`
Safety-rule build plan: `../docs/architecture-research/11-safety-core-build-plan.md`

## Status

| Piece | State |
|---|---|
| `core/schema.py` — MissionPlan v1 (typed steps, closed vocabulary, plan hash) | ✅ built + tested |
| `core/policy/` — engine + **ALL FIVE WAVES**: shape (SCHEMA/SEQ), envelopes (GEO-04/KIN/GEO-05), geometry (GEO-01/02/03), live state (PWR/TEL/CAP), gates (APR-01, ENV-01, CB-01) | ✅ **SAFETY CORE COMPLETE** (122 tests) |
| `core/geo.py` — haversine + LocalFrame (ENU meters, pymap3d) + Shapely boundary polygon | ✅ built + tested |
| `core/interfaces.py` — **the DroneBackend contract**: TelemetrySnapshot, BackendCapabilities, MediaRef, Preflight, error taxonomy, Protocol | ✅ written (implemented by backends next) |
| `core/approval.py` — hash-bound, TTL'd, live-report-only approvals; typed real-flight confirmation | ✅ built + tested |
| `core/policy/dispatch.py` — the pre-dispatch gate: APR-01 + ENV-01 + live re-check + CircuitBreaker | ✅ built + tested |
| `core/events.py` — append-only SQLite audit log; gapless replay | ✅ built + tested |
| `core/engine/` — **the mission state machine + executor**: evidence-gated steps, abort that preempts, deterministic failsafe recovery, portable waypoint-ring orbit, idempotent retries | ✅ built + tested |
| `backends/fake/` — deterministic practice drone with full fault scripting | ✅ built + tested |
| **⇒ M1 IS FUNCTIONALLY COMPLETE: an approved plan flies end-to-end on the fake drone** (134 tests) | ✅ |
| Next: LLM planner (M2) → PX4 SITL backend (M2–M3) → dashboard (M4) | ⏳ |
| `backends/` (Fake → PX4/MAVSDK → Olympe), `planner/`, `server/`, `ui/` | ⏳ upcoming milestones |

## Run the tests

```bash
cd drone-mission
python3 -m venv .venv && source .venv/bin/activate   # or: uv venv && source .venv/bin/activate
pip install -e ".[dev]"                               # or: uv pip install -e ".[dev]"
pytest -q
```

Expected: `134 passed`. (A handful of python-statemachine `current_state` deprecation
warnings are known-cosmetic.) The fun ones are the evil suites across `tests/test_rules_wave*.py` —
sixteen deliberately dangerous missions and states ("skip landing", "neighbor's yard", "orbit the whole
block", "bow-tie boundary", "dead battery launch", "yesterday's data", "everything wrong at once"...),
each asserted to die on the *exact* rules that should catch it.

Key concept added in Wave 4: **static vs live reports.** `validate_plan(plan)` judges the plan alone
(`live_checked=False` — fine for planning/tests, can never authorize flight); `validate_plan(plan, ctx)`
adds the drone's real state — and missing/stale telemetry or capabilities is a *violation*, not a skip.

## Design rules (do not bend)

1. The LLM only ever produces a `MissionPlan`. Unknown actions/fields = parse failure (`extra="forbid"`).
2. Every safety rule is a pure function `MissionPlan -> list[Violation]`, registered in `core/policy/engine.py`,
   with ≥1 pass and ≥2 fail tests. Any violation blocks approval — no severity ladder in v1.
3. `core/` imports no drone SDKs, ever. Backends adapt; the core doesn't know PX4 from Parrot.
4. Approvals bind to `compute_plan_hash(plan)` — edit anything, re-approve everything.
