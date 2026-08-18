Verdict: this is a strong simulator-first capstone with a genuinely good architecture, but it is not ready for physical-aircraft use. Three invariants are verified; seven are broken or inconsistent. The existing suite is green, but targeted probes reproduced safety failures the suite misses. No files were changed.
Critical
Circuit breaker and dispatch gate can be bypassed.
The executor gates once per top-level step at [executor.py (line 222)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:222), but an orbit directly emits multiple backend.goto() and capture_photo() calls at [executor.py (line 346)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:346) without further telemetry, override, or breaker checks. Retries likewise do not recheck the gate.
Recovery is worse: [executor.py (line 481)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:481) directly sends RTL and land while the breaker remains open, contradicting the comment that recovery never bypasses it. The HTTP breaker endpoint merely latches state at [app.py (line 319)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:319); it does not interrupt the current operation.
A read-only probe tripped the breaker during a hung orbit and observed:
RESULT failed failed
COMMANDS_AFTER_TRIP 41
ACTIONS_AFTER_TRIP ['capture_photo', 'goto', 'land', 'return_home']
Why it matters: the kill switch can allow dozens of later backend commands.
Fix direction: route every backend call—including orbit subcommands, retries, tail commands, and recovery—through one wrapper that checks the breaker immediately before dispatch. Explicitly exempt only abort_motion if desired.
Abort/recovery is not reliably preemptive.
The state machine permits abort only from executing or paused at [machine.py (line 42)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/machine.py:42). If abort cancels an active planned RTL or landing, recovery unconditionally calls begin_return() at [executor.py (line 479)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:479), causing an illegal returning → returning or landing → returning transition.
Reproduced during RTL:
RAISED TransitionNotAllowed Can't Begin return when in Returning.
STATE returning
AIRBORNE True
Recovery commands also have no outer watchdog at [executor.py (line 405)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:405) and [executor.py (line 481)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:481). A hung recovery probe remained airborne in returning.
Most seriously, abort() writes to SQLite before setting the event or cancelling work at [executor.py (line 119)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:119); the HTTP route performs another write first at [app.py (line 301)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:301). A simulated audit failure produced:
ABORT_RAISED OperationalError
ABORT_EVENT_SET False
COMMAND_TASK_CANCELLING 0
hold() is also only a flag checked between steps at [executor.py (line 126)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:126), so it cannot immediately stop a long goto/orbit.
Fix direction: preempt first, audit afterward on a best-effort path; add state-aware recovery transitions and strict watchdogs around abort, hold, telemetry, RTL, and land.
Approval is not actually bound to the report that validated the plan.
ValidationReport.ok uses all(...) at [types.py (line 43)](/Users/mike/Desktop/capstone_drone/drone-mission/core/policy/types.py:43), so an empty result list is vacuously valid. live_checked is merely caller-supplied data. grant_approval() checks those booleans at [approval.py (line 78)](/Users/mike/Desktop/capstone_drone/drone-mission/core/approval.py:78), then hashes the separately supplied plan at [approval.py (line 100)](/Users/mike/Desktop/capstone_drone/drone-mission/core/approval.py:100). The report contains no plan hash or required-rule manifest.
A forged empty report approved a plan violating its speed limit; dispatch returned:
FORGED_REPORT_DISPATCH_VIOLATIONS []
The normal hash comparison itself is correct, but it binds approval to the plan—not to proof that this plan passed static validation.
The HTTP approval body also contains only an operator at [app.py (line 55)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:55); the browser does not submit the displayed hash at [index.html (line 246)](/Users/mike/Desktop/capstone_drone/drone-mission/server/static/index.html:246). Concurrent planning can therefore replace the reviewed pending plan before approval.
Fix direction: include plan_hash and the complete expected rule set in ValidationReport; reject incomplete/mismatched reports; require the client to submit the displayed mission ID and hash.
PX4 telemetry fails open when critical streams disappear.
PX4 computes freshness from only critical keys still present—if k in self._cache—at [backend.py (line 181)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:181). Missing state is then synthesized as safe-looking values: armed=False, in_air=False, link_ok=True at [backend.py (line 198)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:198).
Reproduced with a fresh position but missing in_air:
MISSING_IN_AIR_RETURNS_SNAPSHOT True
SYNTHESIZED_IN_AIR False
SYNTHESIZED_LINK_OK True
SNAPSHOT_AGE 0.1
Recovery interprets not tel.in_air as permission to skip recovery at [executor.py (line 472)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:472). _landed_evidence() at [executor.py (line 452)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:452) also ignores telemetry freshness; normal landing evidence checks altitude and vertical speed but not in_air.
Fix direction: require every safety-critical stream with per-field freshness, represent unknown as unknown, and make all touchdown/recovery decisions use the same freshness-checked evidence function.
PX4 may ignore the approved speed and still report success.
At [backend.py (line 280)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:280), failure of set_current_speed() is swallowed with except Exception: pass; goto_location() is sent anyway at [backend.py (line 285)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:285).
Probe result:
GOTO_SENT_AFTER_SPEED_REJECTED 1
METHOD_REPORTED_SUCCESS True
A tightened plan limit can therefore be bypassed by the firmware’s existing/default cruise speed.
Fix direction: treat inability to establish the requested speed as CommandRejected, or prove and enforce a conservative fallback at or below the approved limit.
PX4 idempotency does not protect ambiguous retries.
The contract promises repeated keys will not repeat actions at [interfaces.py (line 138)](/Users/mike/Desktop/capstone_drone/drone-mission/core/interfaces.py:138). PX4 only records a key after completion at [backend.py (line 457)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:457). For goto, the command is sent at line 285, evidence is awaited, and _done(idem) occurs only at line 298.
If PX4 accepted the command but evidence times out, retry sends it again:
PX4_GOTO_SIDE_EFFECT_CALLS_SAME_KEY 2
KEY_MARKED_COMPLETED False
Existing tests only prove repeated keys after successful completion and that retries reuse the same string.
Fix direction: use an atomic in-flight/completed registry storing command identity, arguments, and reusable result/future; reconcile ambiguous vehicle state before resending.
Untyped failures can leave the aircraft airborne in a nonterminal state.
Only BackendError is caught at [executor.py (line 233)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:233). Gate and preflight operations occur before the main try at [executor.py (line 163)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:163), while PX4 capture filesystem operations at [backend.py (line 329)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:329) can raise untyped errors.
A scripted RuntimeError produced:
UNTYPED_RAISED RuntimeError
UNTYPED_STATE executing
UNTYPED_AIRBORNE True
UNTYPED_LAST_EVENT mission.closed
The dashboard wrapper at [app.py (line 283)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:283) only closes the log; it does not convert task exceptions into a visible terminal result.
Fix direction: place the whole execution lifecycle inside one exception-to-terminal-state boundary, translate all adapter failures into the declared taxonomy, and invoke bounded failsafe handling where airborne state is known.
HTTP authentication/operator edge cases violate the stated contract.
require_token() removes the Bearer prefix only if present at [app.py (line 127)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:127), so a bare valid secret is accepted. Operator models enforce only min_length=1 at [app.py (line 50)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:50), allowing whitespace-only identities.
Reproduced:
BARE_TOKEN_STATUS 200
WHITESPACE_OPERATOR_STATUS 200
MISSING_STATUS 401
This is not a secret-token bypass—the correct secret is still required—but it breaks the bearer-token and named-operator invariants. Hold/resume operators are also discarded rather than audited.
Fix direction: parse the scheme strictly and use one normalized, stripped, nonblank operator type at both HTTP and domain boundaries.
Important
Planner reliability: _agent.run() has no timeout or exception boundary at [planner.py (line 75)](/Users/mike/Desktop/capstone_drone/drone-mission/planner/planner.py:75), contradicting “the planner never raises.” Failed planning does not clear an older pending_plan before returning at [app.py (line 222)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:222), and concurrent plan requests are not serialized. Add a bounded timeout, explicit failure result, session lock, and clear/replace pending state atomically.

Audit trail is incomplete: logging starts only after approval at [app.py (line 272)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:272). The exact plan/hash, planner output, validation reports, approval grant/operator/profile, breaker operations, stream deaths, and hold/resume operators are absent. approval.activated records only an ID at [executor.py (line 191)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:191). Mission IDs have second-level precision at [app.py (line 212)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:212), allowing histories to collide. Record the complete governance chain before flight using collision-resistant IDs.

Append-only is API-level, not tamper-proof: [events.py (line 51)](/Users/mike/Desktop/capstone_drone/drone-mission/core/events.py:51) exposes only append/replay, which is good, but SQLite has no trigger/permission preventing update/delete, and server code reaches directly into log._conn at [app.py (line 338)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:338). Add an explicit query API and integrity chaining/signatures if “immutable” is part of the defense claim.

Declared failsafe policy is mostly unused: GPS hold timing, link-loss behavior, low-battery action, and stale-failsafe timing are defined at [schema.py (line 62)](/Users/mike/Desktop/capstone_drone/drone-mission/core/schema.py:62), but execution sends generic abort/RTL/land at [executor.py (line 435)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:435). PX4 always reports manual_input_detected=False at [backend.py (line 216)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:216), and override checks occur only between steps. Either implement the documented policy or remove fields/claims until implemented.

PX4 capabilities are overstated: it advertises gimbal and bracket3/bracket5 support at [backend.py (line 83)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:83), but gimbal errors are swallowed and marked complete at [backend.py (line 315)](/Users/mike/Desktop/capstone_drone/drone-mission/backends/px4_mavsdk/backend.py:315), while capture writes one JPEG regardless of bracket mode. Detect capabilities honestly and fail typed rather than silently degrading.

Orbit capture accounting still fails at legal dense cadence: capture forecast allows 10° cadence, but the executor uses roughly 12° segments and at most one capture per waypoint at [executor.py (line 329)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:329). A 360°/10° probe completed while producing 32 media items versus 37 forecast. Generate capture angles directly or permit multiple cadence crossings per segment.

Endurance estimation is not consistently conservative: partial-orbit captures use a different formula at [rules_wave4.py (line 79)](/Users/mike/Desktop/capstone_drone/drone-mission/core/policy/rules_wave4.py:79), and orbit exit position is approximated as the center rather than the actual ring exit. Reuse orbit_capture_count() and the actual path compiler.

Async and lifecycle gaps remain: timed-out tasks are cancelled but not awaited before retry at [executor.py (line 275)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:275); synchronous SQLite commits occur on the flight event loop at [events.py (line 51)](/Users/mike/Desktop/capstone_drone/drone-mission/core/events.py:51); and server shutdown never aborts an active mission or calls backend.disconnect() after Uvicorn exits at [__main__.py (line 53)](/Users/mike/Desktop/capstone_drone/drone-mission/server/__main__.py:53).

Abstraction leaks: the core/backend dependency direction is clean, but the server reads backend-specific cfg.media_dir at [app.py (line 190)](/Users/mike/Desktop/capstone_drone/drone-mission/server/app.py:190), executor private state, and EventLog’s private connection rather than using the declared protocols.

Minor
The suite emits 110 current_state deprecation warnings; examples originate at [executor.py (line 316)](/Users/mike/Desktop/capstone_drone/drone-mission/core/engine/executor.py:316).
The hold test’s backend assertion is vacuous because it ends in or True at [test_hardening_d10.py (line 155)](/Users/mike/Desktop/capstone_drone/drone-mission/tests/test_hardening_d10.py:155).
ExecutorTuning.poll_interval_s is defined but unused; dotenv/model selection is duplicated between the two demos.
README status is stale and overclaims completion: it says “SAFETY CORE COMPLETE” at [README.md (line 14)](/Users/mike/Desktop/capstone_drone/drone-mission/README.md:14), calls the dashboard upcoming at [README.md (line 30)](/Users/mike/Desktop/capstone_drone/drone-mission/README.md:30), and expects 180 tests at [README.md (line 42)](/Users/mike/Desktop/capstone_drone/drone-mission/README.md:42).
Invariant status
#	Status	Evidence
1	Verified in code	Static import scan found no MAVSDK/Olympe/pymavlink/backend imports under core/.
2	Verified in code + tests	PlanDraft exposes only summary/steps at [planner.py (line 35)](/Users/mike/Desktop/capstone_drone/drone-mission/planner/planner.py:35); envelope injection occurs at [planner.py (line 83)](/Users/mike/Desktop/capstone_drone/drone-mission/planner/planner.py:83).
3	Verified in code + tests	All 14 Wave 1–4 rules are source-pure and registered at [engine.py (line 36)](/Users/mike/Desktop/capstone_drone/drone-mission/core/policy/engine.py:36); each has pass/fail coverage.
4	Broken/inconsistent	Canonical hash comparison works, but approval does not bind the validation report to that plan.
5	Broken	Core rules deny missing whole snapshots, but PX4 synthesizes missing critical fields and recovery trusts stale state.
6	Broken	Gate is per top-level step, not immediately before every backend call; breaker/recovery bypasses exist.
7	Broken	Ordinary executing-step abort works, but RTL/landing abort, audit failure, and hanging recovery do not preempt safely.
8	Broken	Resume runs the full gate, but recovery dispatches RTL/land through an open breaker.
9	Broken/inconsistent	Every named route has the dependency, but bare-token and whitespace-operator cases pass.
10	Broken	Completed-command dedupe exists; accepted-but-unconfirmed retries can repeat PX4 commands.


Clean systems checks: the fixed server startup now builds PX4 and serves Uvicorn on the same loop at [__main__.py (line 35)](/Users/mike/Desktop/capstone_drone/drone-mission/server/__main__.py:35); WebSocket disconnect affects only the UI, not the independent mission task; the LLM is not consulted after mission execution starts; RTSP capture correctly moves blocking OpenCV work off-loop.
Verification run
env PYTHONDONTWRITEBYTECODE=1 /Users/mike/.venvs/drone-mission/bin/pytest -q -p no:cacheprovider
187 passed, 6 skipped, 110 warnings in 1.17s

/Users/mike/.venvs/drone-mission/bin/ruff check --no-cache core backends planner server demo tests
All checks passed!
The six skipped tests are the live-PX4 contract cases, so this review did not independently re-certify SITL.
Mypy, run with cache disabled, did not pass:
Found 6 errors in 4 files (errors prevented further checking)
Those were primarily missing third-party stubs plus a Python-3.11 target/Numpy-stub incompatibility, not six confirmed runtime bugs.