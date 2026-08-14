# 09 — MVP and Ten-Month Roadmap

**Status:** v1.0 — Phase 7 complete, 2026-08-14. MVP definition: docs 00 §2 / 01 §6 (unchanged). Assumes 3 students × ~12 h/wk average, Sep 2026 → Jun 2027, capstone demo/defense in May–Jun 2027. Every milestone ends in something demonstrable; no milestone depends on hardware that hasn't cleared its gate.

---

## 1. Roles (rotate for learning; owner = accountable, not sole author)

- **R1 Mission core & safety (Mike):** schema, shot library, policy engine, state machine, events/audit — the layers he must defend in orals.
- **R2 Backends & simulation:** FakeBackend, PX4Backend/MAVSDK, gz world, Docker/CI, Sphinx/Olympe (post-G2), fault drills.
- **R3 Product & planner:** dashboard, approval UX, WebSocket telemetry, planner prompts + eval set, media pipeline, STT.

## 2. Month-by-month

**M0 — Sep 2026 (setup + spikes; kills the biggest unknowns first)**
Deliverables: repo scaffold per 08 §2; dev-env docs; PX4 SITL+gz headless in Docker on at least one machine; **Spike-1** gz camera-topic frame grab saved to JPEG; **Spike-2** PydanticAI → valid MissionPlan on 5 canned requests (cloud + Ollama); MDS single-drone SITL demo reproduced once (isolated, read-only — learning + CLAUDE.md step 2); G1 decision brief signed; **G2 laptop prep** (G2 already resolved — Mike's NH58AF/RTX 2070): confirm Ubuntu 20/22/24 on the Linux partition, disable Secure Boot, install NVIDIA proprietary drivers, then install Sphinx and run the week-1 Sphinx spikes (camera2 capture + media download) early instead of waiting for M5.
Acceptance: `docker compose up sitl` + `pytest -m unit` green on all three laptops; two spike screenshots/logs in repo.
*Rollback:* if Spike-1 fails → typhoon_h480/Classic is banned; fallback = screen-space capture via gz GUI API or Webots sandbox for camera work while PX4 path continues motion-only (re-scored at M1 review).

**M1 — Oct 2026 (the governed core, no drone at all)**
Deliverables: `core/` schema v1 + geo module + policy engine (full rule catalog 08 §4) + state machine + event store; FakeBackend with fault scripting; abort-preemption proven in tests.
Acceptance: ≥90% branch coverage on core/; table-driven rule tests (every rule has ≥1 pass + ≥2 fail cases); scripted GPS-loss/battery/timeout scenarios produce the exact event trajectories from 10 §3.

**M2 — Nov 2026 (language in front, PX4 underneath)**
Deliverables: planner with repair loop + eval set (≥20 requests incl. adversarial); plain-language brief; PX4Backend motion: preflight/takeoff/goto/RTH/land in gz world with House 1; contract-test suite runs on Fake + PX4.
Acceptance: planner eval ≥95% schema-valid within 2 repair rounds; unsafe intents rejected by *validator* (demo artifact); contract suite green on both backends.
Gate check: **G2 must be resolved this month** for the stretch track to stay alive (MVP unaffected either way).

**M3 — Dec 2026 (photography happens; half-time demo)**
Deliverables: orbit compiler (ring + yaw-to-center + gimbal pitch) executed on PX4; capture-at-angle with gz frame grab + EXIF + step association; shot library v1 (orbit package, front/rear elevated, lot overhead); minimal dashboard (map, state, telemetry, approve).
Acceptance + **mid-project demo:** typed request → brief → approve → SITL flight orbits the house, 8+1 images land in the gallery tied to steps → RTH → replayable timeline. This is MVP-shape end-to-end.

**M4 — Jan 2027 (make it defensible: faults, audit, CI)**
Deliverables: full fault-drill suite via PX4 `failure` (gps/link/battery) + operator hold/abort/override paths wired to UI; approval TTL + plan-hash binding + ENV-01 profile gate; event-log replay view; CI: unit+contract per PR, one SITL scenario per PR, nightly matrix.
Acceptance: each of the 7 failure-mode rows in 10 §3 demonstrated from the UI with its event trace; CI badge green two consecutive weeks.

**M5 — Feb 2027 (stretch track A: the ANAFI path in simulation)** *(enters only if G2 done; else M5 = polish + M6 pulled left)*
Deliverables: Sphinx installed; **Spike-3** camera2 photo + olympe.Media download in-sim (OQ-1) + extended_move_to behavior (OQ-3) + OA interplay (OQ-2); OlympeBackend passing the contract suite on Sphinx.
Acceptance: the *identical* M3 mission JSON executes on Sphinx virtual ANAFI Ai with real media downloaded (**Gate G4 evidence**).

**M6 — Mar 2027 (stretch track B: bounded physical flight)** *(enters only through G5)*
Deliverables: G5 checklist executed (Part 107 holder as RPIC, private property permission, Remote ID, wind limits, rehearsed piloting-source override on the ground, flight cards); 2–3 bounded flights: manual shakedown → autonomous takeoff/goto/RTH at ≤30 m alt/≤20 m radius → full mini-mission if margins hold.
Acceptance: physical mission event log + media archived; zero manual-override surprises (override drill executed intentionally once in-air at safe altitude).
*If G5 never opens:* capstone stands on M4+M5; this month becomes hardening + user testing.

**M7 — Apr 2027 (product polish + evaluation)**
Deliverables: media export to MLS spec; deterministic IQA trio (blur/exposure/tilt) flagging retake candidates [pull-forward from POST if time]; 3 external-user test sessions (agent/photographer personas) with findings; performance pass (NFR2 numbers measured).
Acceptance: a stranger completes a mission unaided in <10 min; NFR2 met.

**M8 — May 2027 (freeze + defense)**
Deliverables: code freeze week 2; final docs (architecture-as-built diff vs this folder); demo script + recorded backup video (sim + physical if achieved); defense deck; FINAL_RECOMMENDATION updated to "as delivered."
Acceptance: two full dress rehearsals, one with injected GPS-loss live.

**Jun 2027 — buffer.** Deliberately unplanned (absorbs slips; history says it will).

## 3. Critical path & float

`M0 Spike-1 → M1 core → M2 PX4 motion → M3 orbit+capture → M4 faults/CI` is the MVP spine — no gate can block it (all-sim, all-free). Stretch spine `G2 → M5 Sphinx → G4 → G5 → M6` hangs off it independently. Planner/UI work (R3) parallels the spine with slack; the schema (M1) is the only hard cross-team dependency — freeze schema v1 at M1 exit, version changes after that.

## 4. Weekly cadence

Monday 30-min sync (demo-or-blocker format); PR review within 48 h (owner ≠ reviewer); every Friday: one-command demo of the current slice from a clean checkout; RESEARCH_LOG entry per week; monthly gate/risk review against doc 10 (re-score, not re-litigate).

## 5. Budget picture (all G6-tracked; commitments need sign-off)

Required for MVP: $0 (all-sim, OSS, free-tier tiles, local or low-cost LLM — expect <$20/mo API spend during M2–M4). Stretch: **Linux/GPU machine $0 — covered by Mike's existing Clevo/Sager NH58AF (G2 resolved)**; Part 107 exam ~$175 if no holder available (G5, R13); incidental props/SD cards <$50. No aircraft purchases (G3 dormant).

## 6. Exact point bounded physical testing may begin

All of: M4 acceptance met (fault drills demonstrable) ∧ G4 passed (identical mission on Sphinx incl. media) ∧ G5 checklist signed by Mike + RPIC ∧ weather within limits. Earliest calendar slot: March 2027. Physical tests add **margin, never new behavior** — anything unproven in Sphinx is out.
