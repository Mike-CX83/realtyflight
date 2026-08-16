# RealtyFlight — Build Journal

**What this is.** The running story of RealtyFlight — Mike Hankins' Atlas School capstone: an AI-governed real-estate photography drone — and the memory file that lets any future AI session pick up where the humans left off.

**How the repo's three memory files divide the work:** `CLAUDE.md` is the rules (how any AI agent must behave here). `TODO.md` is the live state (what is done, in progress, and next — the authoritative ledger). `JOURNAL.md` is the narrative memory: what happened, what broke, what was decided, by whom, and why. TODO looks forward; the journal looks back.

**How to use it.** Humans: read Part I like a story; Parts II–III are the receipts. AI sessions: read `CLAUDE.md` → `TODO.md` → Part IV here, then skim Part I if you need the why behind a decision. At the end of any session that changed something durable, append a dated entry to Part I and refresh Part IV. Never write secrets here — no API keys, no tokens, ever.

**The one-line architecture:** language proposes → rules decide → a human authorizes → a state machine flies.

**The one-line meta-story:** the build process mirrors the product. The AI drafts, deterministic tests judge, and Mike is the human approval gate — the same governance pattern the drone runs, applied one level up to its own construction.

---

## Part I — The Story

### Prologue — the mission (before August 14, 2026)

Mike Hankins, a software engineering student at Atlas School in Tulsa, sets the capstone: tell a drone in plain English what real-estate photos you want; an LLM turns intent into a typed mission plan; deterministic safety rules validate it; a human approves it; only then does anything fly — in simulation first, and eventually on real aircraft. On hand at kickoff: a Parrot ANAFI Ai (bought for exactly this), a Clevo/Sager NH58AF gaming laptop (Ryzen 7 3800XT, RTX 2070, 32 GB, dual-boot Windows/Linux) as the future simulation rig, a MacBook Air as the daily driver, and Cliff Flock — a Part 107–certificated pilot who is also an L3 network engineer at Google — as the identified remote pilot in command for physical flights. Mike wrote a seven-phase master architecture prompt, opened a Claude Cowork session, and handed it over with one instruction: this is your prompt — execute it.

### Chapter 1 — Research day (Aug 14)

One day, thirteen documents (`docs/architecture-research/00–12` plus a final recommendation and a research log). Claude inventoried and audited the five drone repos already in the workspace, mapped the open-source landscape, compared simulators, assessed the ANAFI Ai path, and drafted the target architecture and a ten-month roadmap with explicit decision gates and a risk register. The audit surfaced license landmines early, before any code was written: the strongest existing system (MDS / mavsdk_drone_show) is PolyForm-Noncommercial — read, never copy; several tempting repos are unlicensed or closed — never republish; Ultralytics and ODM are AGPL; QGroundControl's mission math is dual-licensed, so any port elects Apache. The reuse philosophy settled here: take the recipe, not the groceries. Dependencies are declared in `pyproject.toml` (the hundred-thousand-plus lines of PX4, MAVSDK, Gazebo, Pydantic and friends live in the venv and the Docker image, never in the repo), and reference repos are quarantined read-only.

### Chapter 2 — The fork: MDS or greenfield (Aug 14)

Gate G1: adopt MDS as the chassis, or build a lean governed core and borrow only ideas. Mike made the call — "we are going with your suggestion" — greenfield-lean. Then he pushed in the other direction: "lets make sure you have not missed anything." A second, deeper open-source discovery round ran (doc 12 and the round-2 delta), pinning exact commits of RoboGuard, SPINE, AUSPEX, droneroute, map-creator, and Aerialist as references. The gap closed further; the verdict held. Decision provenance: Mike decided, the research recommended, and both are written down.

### Chapter 3 — Five waves in a day: the safety core (Aug 14)

Built to the plan in doc 11, one command at a time — "start wave 1," then "next wave" four times. Wave 1: the typed MissionPlan schema — a closed vocabulary of eight step types, unknown fields forbidden, plus a canonical plan hash. Wave 2: envelope rules (altitude, speed, distance-from-home, step and capture budgets). Wave 3: boundary geometry — real planar math (ENU local frame via pymap3d, Shapely polygons) so "stay inside the property" is geometry, not vibes. Wave 4: live-state rules with the project's defining posture, deny-by-default — missing or stale telemetry is a violation, never a skip, and a static-only validation can never authorize flight. Wave 5: the gates — approvals bound to the plan hash with a 300-second TTL (edit anything, re-approve everything), a typed "I AUTHORIZE REAL FLIGHT" phrase for physical aircraft, a pre-dispatch gate that re-checks reality before every command, and a manual circuit breaker that beats everything and only a named human can reset. Fifteen rules, 122 tests, and a suite of ~20 deliberately evil scenarios ("skip landing," "neighbor's yard," "dead-battery launch," "approve-then-edit") each asserted to die on the exact right rule.

### Chapter 4 — The executor: an approved plan flies, on a fake drone (Aug 14)

An append-only SQLite event log with gapless sequence numbers (the log alone can replay a mission), a 13-state mission state machine (illegal jumps are impossible by construction), and an executor that demands evidence: telemetry proof of arrival, altitude, and touchdown before any step counts as done. Abort actually preempts — it cancels a hung command mid-await and flies home. Failsafe recovery is deterministic. Retries are idempotent and bounded, reusing the same idempotency key. The orbit is portable by design: a waypoint ring with yaw-to-center and capture angles, so any backend that can fly to a point can fly an orbit. A scriptable FakeBackend (hangs, timeouts, battery crashes, stick input) made all of it testable. The tests caught two real bugs the same day they were written: the orbit photographed its 360° seam twice (ten photos where nine were promised), and the fake backend marked *failed* attempts as completed, silently breaking retry semantics. 134 tests.

### Chapter 5 — Going public: realtyflight (Aug 14)

The name came from a misread: Claude read a message as "realityflight"; Mike was spelling *realty*. Realty + flight — the pun holds, the domain checked out, and `github.com/Mike-CX83/realtyflight` was born, MIT-licensed, with a `.gitignore` fencing off everything that must never ship: the reference repos, the research clones, `.env`, venvs, media. Division of labor established: Claude stages and commits through the device bridge; Cursor's agent (in Mike's IDE) verifies on the real machine and pushes. First commit: 53 files. This chapter also introduced the project's recurring antagonist — the MacBook Air's disk. iCloud's "Optimize Mac Storage" kept evicting project files to the cloud mid-operation (reads failing with deadlock errors), at the worst moment evicting files *between add and commit*; Claude re-materialized 35 files from its cloud copies and committed fast. Foreshadowing, appearance one of four.

### Chapter 6 — The planner: language becomes a typed plan (Aug 14)

The LLM layer, built deliberately small. The model's output type contains *only* steps and a summary — the mission envelope (boundary, limits, identifiers) is injected server-side, so the LLM physically cannot touch it. Failed validations feed the exact rule violations back for at most two repair rounds; a hopeless model yields an honestly failing report, which Wave-5 approval then refuses. Adversarial requests ("the neighbor's yard at max speed") die in the validator, never in the prompt. All of it proven offline with scripted FunctionModels — no API key needed in CI. 140 tests.

### Chapter 7 — First contact (Aug 14)

The evening earned the small comedy every real project gets: `pip: command not found` (fixed with a venv), then a 401 from a leftover `export ANTHROPIC_API_KEY=your_key_here` placeholder (fixed with `unset`). Then Mike typed a plain-English request into `python -m planner.demo`, and gpt-5.1 answered with an eleven-step mission — elevated front three-quarter at 18 m with −20° gimbal, a full orbit at 25 m radius with bracketed exposures every 45°, an overhead lot shot at 35 m looking straight down, return home, land. All ten static rules: PASS. Repair rounds needed: zero. The thesis — language proposes, rules decide — demonstrated live on the first try.

### Chapter 8 — The PX4 adapter and the portability proof (Aug 14)

`backends/px4_mavsdk/` translates every mission step into MAVSDK calls with evidence waits (arrival, altitude, touchdown), converts relative altitude to AMSL against the captured home altitude, controls the gimbal defensively across API versions, and captures honestly — synthetic evidence JPEGs with telemetry sidecars now, a real RTSP frame-grab path plumbed for later. The philosophical core is `tests/test_backend_contract.py`: ONE suite that runs identically against the fake drone and PX4. Passing it means the mission engine cannot tell backends apart — that file is the portability claim. 146 tests, plus 6 gated behind a live simulator.

### Chapter 9 — The Docker wall (Aug 14, evening)

The last thing between the code and simulated physics was one Docker container, and the Mac fought: daemon not running (the app had never launched), then a corrupt VM disk on first boot, a factory reset accidentally interrupted and restarted, an engine stuck on "Starting…" — and finally `df -h /` told the whole story: **7.4 GB free**, where Docker wants 15–20. The same shortage behind the iCloud evictions of Chapter 5. Diagnosis over guesswork: no amount of resetting fixes a full disk. Mike chose to clean the Mac rather than move machines, freed the space, and the wall came down.

### Chapter 10 — Smoke (Aug 14, late)

`python -m backends.px4_mavsdk.smoke` against the SITL container — which, anticlimactically, just worked (the image auto-targets Docker Desktop's host address). Connect → preflight → takeoff to 10 m (8.5 m evidence) → a ~30 m leg (2.2 m arrival evidence) → photograph → RTL → land → `SMOKE FLIGHT COMPLETE`. Then the payoff: `RUN_PX4_CONTRACT=1 pytest` — the same six contract tests that certify the fake backend, now green against real PX4. And the night's lesson: the smoke flight caught a real adapter bug no unit test could — MAVSDK reports battery as 0–100, the adapter multiplied by 100 anyway, and the first live telemetry read announced a 10,000% battery, which the schema promptly rejected. 146 unit tests had passed while the adapter was broken against reality. That is exactly the class of bug the smoke test exists to catch, and exactly why this project is simulation-first. (Also fixed this night: pip installs into the iCloud-synced Desktop crawled to a standstill under sync contention — the working venv moved to `~/.venvs/drone-mission`, outside the synced tree. Disk antagonist, appearance two.)

### Chapter 11 — The night it all flew: D7 (Aug 14)

One command: `python -m demo.fly "Photograph this property: orbit the house, full exterior package." --backend px4`. The full governed pipeline, live: gpt-5.1 produced a rule-clean eleven-step plan in one round; static Waves 1–3 passed; Wave 4 passed *live* against the real simulated drone's battery, GPS, telemetry, and capabilities; approval granted; and then it flew — takeoff, front three-quarter leg, the orbit drawing itself, the climb to overhead, return, land, touchdown. Audit log timeline: 176 seconds wheels-up to touchdown (the planner had estimated 3.4 minutes). Outcome: completed, 11/11 steps, 10 photos, 48 audit events, exit 0. Mid-flight, reality found another bug the deterministic fake never could: a retried `land` step (touchdown evidence briefly out of tolerance) re-entered the landing state, which the state machine correctly refused — crashing the mission from the sky. The fix was a two-line idempotent-retry guard in the shared engine, found because a *simulated* aircraft was allowed to fail first. Simulation-first vindicated twice in one night.

### Chapter 12 — Real photographs, and the day the safety system said no: D8 (Aug 14–15)

Until now every photo was an honest 161-byte stub. D8 made captures real: an RTSP frame-grabber that reads past H.264 keyframe warm-up, verified against a live stream in the cloud and against the Gazebo camera vehicle on the Mac — real ~28 KB renders of sky and ground, not stubs. Two more real bugs found and fixed on the way: MAVSDK's helper server process leaked on disconnect (breaking the *next* run with "Address already in use"), and a failed recovery flight crashed the process uncaught instead of ending in a recorded FAILED state.

Then the interesting failure. Five live camera-vehicle flights, five refusals — the camera rendering pins the container at 340–486% CPU on the Air, telemetry goes stale, and the Wave-4 rules (TEL-01, PWR-01/02) deny the flight. The system was working exactly as designed: it refused to fly on stale data. The tempting fix was one number — lengthen the staleness tolerance and the demo passes. **Mike's decision, 2026-08-15: no. No safety thresholds change to make a demo work.** D8 is parked until the Linux/RTX machine runs the camera vehicle natively (checklist item A7 holds the exact re-run recipe), and `--camera synthetic` stays the Mac default. Demo pressure lost; deny-by-default won. This is the single best story in the project so far, because it is the thesis *enacted*: the governance held against its own author.

(Disk antagonist, appearances three and four: Docker Desktop's disk limit was effectively the whole drive, and five hours of container churn filled it — ENOSPC on everything, VM hang, force-quit — and the disk-full event triggered another round of iCloud evictions. Countermeasures now standing: cap Docker's disk limit; back up to GitHub before anything else in a new session.)

### Chapter 13 — The shot library and outside eyes: D9, D10 (Aug 15)

D9, the photography brain: `planner/shots.py` — front elevated three-quarter, exterior orbit, rear elevated, lot overhead — with bearings, standoffs, and gimbal pitch *computed from property geometry* ("front" is the side facing launch). `Goto` gained an optional `yaw_deg` so static shots face the structure; the system prompt now teaches the catalog so live LLM plans converge to library shapes; the library has no safety authority — its output faces the full validator like anyone else's. Cloud-verified at 158 tests; the live PX4 run is queued.

Same day, outside eyes: an external code review (ChatGPT, repo-only) produced findings Claude verified against source and adopted as D10 — a hardening pass with a feature freeze until done. Highlights: recovery must never declare "completed" without landed *evidence*; the geofence rule checks waypoints but not the straight segments between them (a concave boundary could be legally entered and illegally crossed); `Hold` must actually hold; capture forecasting and execution must share one counting function; the RTSP grab must leave the telemetry event loop. Plus repo health (README, CI, lint) and a privacy fix: the repo goes private until showcase, because a decision log named a real person publicly. The review's strategic note was kept on purpose: at the defense, explaining cancellation, idempotency, telemetry freshness, and why the LLM cannot command the vehicle beats any new feature. A QGC handoff also queued: QGroundControl watching the same simulated aircraft on a live map — making the demo *watchable* with zero new code.

### Chapter 14 — Beyond the code (Aug 15)

Mike is founding Atlas's first drone racing team — which doubles as this project's hardware pipeline. Two build tracks, two firmwares: racing birds on Betaflight (recreational — TRUST test), and AI-capable builds on PX4-compatible flight controllers that drop straight onto the existing `PX4Backend`, making a team-built quad a first-class candidate for the physical target. The regulatory reality got verified and written down: any commercial use requires Part 107 regardless of aircraft weight — so the moat is not a weight class, it is the governed architecture itself, plus a ~$175 knowledge test. And the brain-stays-on-the-ground design is exactly what makes small AI aircraft feasible: the aircraft carries an autopilot, a link, and a camera; the intelligence lives here.

And this journal was created — because the story is now long enough to be worth telling, and because the next AI session shouldn't have to rediscover any of it.

### Chapter 15 — Re-cert on the Mac, and a new wall: SITL won't boot (Aug 16)

Handed the D9 and D10 handoffs to run in sequence. The static half went cleanly: a stale `.git/index.lock` (24 hours old, nothing holding it) was clearing every git command out to a 2-minute timeout — removed once `lsof`/`ps` confirmed it was abandoned. From there, `pip install -e ".[dev]"`, `pytest -q` (**180 passed, 6 skipped**, exactly matching the cloud), `ruff check .` (clean), and the keyless demo (exit 0, 11/11 photos, correct catalog tags) all passed on this Mac with both D9's and D10's code on disk together.

Then the SITL half hit a wall — or looked like one. `jonasvautherin/px4-gazebo-headless:1.17.0` — the same tag that flew clean twice on Aug 14 — booted through Gazebo world init and "Spawning Gazebo model," then its console fell into what looked like an infinite prompt-redraw loop (`pxh>` reprinting at high frequency, hundreds of MB of log, ~150% CPU) and never printed "Ready for takeoff!" Reproduced three times, including once after a full clean quit/relaunch of Docker Desktop with the daemon confirmed healthy first. Per the project's own 3-strikes rule, Claude stopped there and wrote the repro up for Mike rather than keep forcing it.

Mike's answer arrived as a file, not a message: `SITL_TRIAGE.md`, a short triage note reasoning from history — the working Aug 14 run had used `-it` (a real TTY), PX4's `pxh>` shell is known to spin redrawing its prompt with no TTY attached, and a "hung boot" console can coexist with a PX4 that's actually up and serving MAVLink underneath. The note gave a four-step check ending in "judge by connection, not console." It was right on the first try: the image digest matched the Aug-14 known-good digest exactly (so not an image change), adding `-t` produced a completely normal, quiet boot log, and `python -m backends.px4_mavsdk.smoke` connected and flew clean. `RUN_PX4_CONTRACT=1 pytest` then passed 12/12, and the D9 live flight followed immediately after: gpt-5.1 planned all four canonical shot-library tags in one round, yaw_deg came through correctly on both static gotos, and the mission flew completed with 11/11 photos — including a retried `land` step (a transient timeout) that succeeded clean on its second attempt, proving the D7 idempotent-retry guard under a real live retry. D9 and D10 both close out `[x]`; the feature freeze lifts.

The lesson worth keeping: the 3-strikes rule said "stop and write it up," not "conclude it's broken." Writing it up precisely — exact commands, exact log signature, exact digest — is what let a second pair of eyes (here, Mike) spot in one read what three live attempts couldn't: the failure was in how the container was being observed, not in the container itself.

One more catch on the way out: the root README (pushed in the D10-era commit) already claimed a CI workflow existed — it didn't; there was no `.github/` directory at all. Wrote the actual workflow (ruff + pytest on push), pushed it, and the first run went green: a small reminder that "the handoff said it's done" and "it's on disk" are different claims, worth checking both.

*(Next entry goes here.)*

---

## Part II — Milestones at a glance

| Date (2026) | Milestone | Evidence |
|---|---|---|
| Aug 14 | Architecture research complete: 13 docs, licenses vetted, gates defined | `docs/architecture-research/` |
| Aug 14 | Gate G1 decided by Mike: greenfield-lean; MDS reference-only | doc 10, FINAL_RECOMMENDATION |
| Aug 14 | Safety core: 5 waves, 15 deterministic rules, evil suite | 122 tests |
| Aug 14 | Executor + fake drone: approved plans fly end-to-end; 2 real bugs caught by tests | 134 tests |
| Aug 14 | Public repo: `github.com/Mike-CX83/realtyflight`, MIT | first commit `6fd1146`, 53 files |
| Aug 14 | LLM planner: envelope injection, bounded repair loop | 140 tests |
| Aug 14 | Live demo: gpt-5.1 plans a valid 11-step mission, first try, 10/10 rules | planner demo transcript |
| Aug 14 | PX4 adapter + one contract suite over fake AND PX4 | 146 tests + 6 gated |
| Aug 14 | **First live SITL smoke flight passes; contract suite green on PX4** | `12 passed`; battery-unit bug found & fixed |
| Aug 14 | **D7: full pipeline flies — NL → LLM → validation → approval → Gazebo physics** | completed, 11/11 steps, 10 photos, 48 audit events |
| Aug 14–15 | D8: real RTSP camera frames verified; live run PARKED by Mike — safety thresholds unchanged | TODO D8/A7; commit `e47d66b`; 149 tests |
| Aug 15 | D9: shot library v1 (4 canonical shots computed from geometry), cloud-verified | 158 tests; live run queued |
| Aug 15 | D10 hardening pass adopted from external review; feature freeze; repo → private | TODO D10 |
| Aug 15 | Atlas drone racing team founded as hardware pipeline; FAA path verified | TODO B5 |
| Aug 16 | **D9 + D10 both complete:** live LLM+PX4 flight (all 4 catalog tags, yaw_deg), SITL contract 12/12 + smoke, CI green, feature freeze lifted | TODO D9/D10 |

## Part III — Challenge log (symptom → root cause → fix)

1. Files unreadable, git crashing (EDEADLK) → iCloud "Optimize Mac Storage" evicting files under disk pressure → download-before-work (`brctl download`), re-materialize from cloud copies, commit fast; long-term: keep heavy trees out of synced folders.
2. `pip install` into the repo venv stalls indefinitely → iCloud sync contention over tens of thousands of small venv files → working venv moved to `~/.venvs/drone-mission`, outside the synced tree.
3. Git refuses to operate in the device VM ("dubious ownership"; index.lock undeletable) → sandbox identity + no-delete mounts → `safe.directory` via env vars; `mv` stale locks aside instead of `rm`.
4. Remote tools refuse to write `.env` → by design (secret hygiene) → Mike writes secrets himself with a local `echo`; `.env` is gitignored; rotate the key after the project.
5. Orbit produced 10 photos when 9 were promised → capture fired at the 360° seam twice → strict `< arc_deg` comparison; test asserts exact counts.
6. Retry test failed: duplicate command was "already done" → fake backend marked *failed* attempts complete → dedupe only on success; idempotency = completed commands only.
7. Demo 401 despite a valid key in `.env` → leftover `export ANTHROPIC_API_KEY=your_key_here` placeholder shadowing it → `unset`, and the provider picker now prefers whichever real key exists.
8. Docker Desktop: corrupt VM disk, factory-reset loop, engine never starts → 7.4 GB free disk vs 15–20 needed → clean the disk first; no amount of resetting fixes full storage.
9. First live telemetry read rejected: battery 10,000% → MAVSDK reports 0–100, adapter multiplied by 100 → 3-line unit fix; lesson: 146 green unit tests can coexist with an adapter broken against reality — hence smoke tests.
10. Mission crashed mid-air on a retried `land` → state machine (correctly) refused re-entering `landing`; retry path never exercised by the too-clean fake → idempotent guard on recovery transitions; found in simulation, where it belongs.
11. Next run after a crash: "Address already in use," split telemetry → MAVSDK's helper server process leaked on disconnect → stop it explicitly in `disconnect()`.
12. Failed recovery flight crashed the process uncaught → no exception handling around the recovery's own dispatch → catch typed backend errors, record `recovery.failed`, end in FAILED — never silently.
13. Camera-vehicle flights refused 5/5: telemetry stale (TEL-01/PWR-01/02) → Gazebo camera rendering pins the Air's CPU at 340–486% → **parked, not patched**: no threshold loosening to pass a demo; re-run on the RTX/Linux machine (A7).
14. Every tool failing with ENOSPC; Docker VM hung → Docker's disk limit was effectively the whole drive; 5 h of churn filled it → force-quit to recover; cap Docker's disk limit; backup-to-GitHub-first rule in every new session.
15. External review found real P0s in "finished" code (recovery-without-evidence; geofence checks points, not paths) → single-author blind spots → adopted as D10 with regression-tests-first and a feature freeze; outside eyes are cheap, crashes are not.
16. Every git command hanging for 2 minutes then failing → a stale `.git/index.lock` (24h old) with nothing actually holding it → confirm via `lsof`/`ps` first, then remove; don't assume a lock file means a live process.
17. PX4 SITL container never printed "Ready for takeoff!" — console looked like it was looping, redrawing its prompt forever → `docker run` had no `-t`; PX4's `pxh>` shell redraw-spins with no TTY attached, which is cosmetic — the drone was actually up and serving MAVLink the whole time → add `-t`; judge SITL readiness by MAVSDK connection (or the smoke test), never by console text alone.

## Part IV — AI context pack (read `CLAUDE.md` and `TODO.md` first — they are authoritative)

**State as of 2026-08-16.** The governed core is real and flying in simulation: schema + 15 rules + hash-bound TTL approval + dispatch gate + circuit breaker (`core/`), evidence-gated executor and 13-state machine (`core/engine/`), append-only audit log (`core/events.py`), fake and PX4 backends behind one contract (`backends/`, `tests/test_backend_contract.py`), LLM planner with server-injected envelope and repair loop (`planner/`), shot library (`planner/shots.py`), one-command demo (`demo/fly.py`). **D9 and D10 are both fully done**: 180 passed / 6 SITL-gated on this Mac, ruff clean, keyless demo green, PX4 contract 12/12, smoke flight clean, and a live LLM+PX4 flight where gpt-5.1 used all four shot-library tags with correct yaw_deg (completed, 11/11 photos). CI is green on push. D7 flew the full pipeline live on gpt-5.1. D8 (real camera) is PARKED → circle-back is A7. The feature freeze from D10 has lifted. Along the way: PX4 SITL looked hung (console prompt-redraw loop) three times before Mike's triage note found the real cause — no `-t` TTY flag, purely cosmetic — a good example of "stop and write it up" working as designed.

**Current queue (TODO footer is the source of truth):** (1) D11 — the dashboard (spec'd in TODO: FastAPI + Leaflet, auth-stubbed-with-real-bones, phone-first, voice via dictation day one); (2) D12 context enrichment and D13 photogrammetry are spec'd but sequenced after D11. Parallel: A1–A3 laptop checks, B2 teammates, B4 showcase date. Standing: cap Docker Desktop's disk limit; always allocate a TTY (`-t`) when running PX4 SITL headless-detached, or judge readiness by connection (smoke test) rather than console text.

**Invariants (do not bend):** `core/` never imports drone SDKs. The LLM only ever produces steps+summary; the envelope is server-injected. Every rule is a pure function with pass+fail tests; any violation blocks approval. Approvals bind to the plan hash. Deny-by-default: missing/stale state is a violation, never a skip; static reports never authorize flight. Recovery bypasses plan gates but never the breaker. Never weaken safety code, validators, approval, or tests to make anything pass. Never commit `.env`, venvs, `media/`, `runs/`, vendor/reference repos. MDS is PolyForm — ideas only, never code.

**Working conventions:** Mike drives from the Mac (venv at `~/.venvs/drone-mission`; `.env` holds the OpenAI key — gitignored, rotate post-project; camera stays synthetic on the Air). Cowork sessions build and verify in the cloud, stage/commit via the device bridge with surgical `git add` (never `-A` blindly), and never force-push; Cursor's IDE agent verifies on-machine and pushes. Slice handoffs are written as `*_HANDOFF.md` in repo root and deleted on completion; durable facts land in `TODO.md`. Three-strikes rule: one error surviving three distinct fix attempts → stop and write it up.

## Part V — How to append

At the end of a work session, add to Part I:

```markdown
### Chapter N — <title> (<date>)
What happened; what was decided and by whom; what broke, its root cause, and the fix
(also add a line to Part III); what's next. Evidence: test counts, commits, log excerpts.
```

Rules: decisions and evidence, not transcripts. Name the decision-maker. Update Part IV's state paragraph and queue. No secrets, ever.

---

*Created 2026-08-15, from the origin thread (research day → safety core → first flights) plus the on-disk record (`TODO.md`, handoffs). Maintained by whoever is at the keyboard — human or AI — under the rules above.*
