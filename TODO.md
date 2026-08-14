# TODO — Living Checklist (start of M0)

**How to use this:** work top-to-bottom; check items off (`[x]`) as you go; when something blocks you, bring the exact error/output back to Claude and we solve it together. This file is the plan — we build on it as you go. (Detailed context: `docs/architecture-research/09` roadmap, `10` gates.)

---

## A. Gaming laptop prep (unlocks Sphinx week-1) — do on the NH58AF's Linux side

- [ ] **A1. Confirm which Linux you have.** Boot Linux, run: `lsb_release -a` (or `cat /etc/os-release`). Sphinx requires **Ubuntu 20.04, 22.04, or 24.04 (x86_64)**. Paste the output to Claude.
  - If it's not one of those → we plan a clean Ubuntu 24.04 install or a new partition (Claude will walk you through it; back up first).
- [ ] **A2. Check Secure Boot is OFF.** Run: `mokutil --sb-state` (want: `SecureBoot disabled`). If enabled → reboot into BIOS/UEFI (usually F2/Del on Clevo) → Security → disable Secure Boot.
- [ ] **A3. NVIDIA proprietary driver working.** Run: `nvidia-smi` — you should see "GeForce RTX 2070" and a driver version. If not: `sudo ubuntu-drivers install` then reboot, re-check.
- [ ] **A4. Basics installed:** `git`, `curl`, Docker (`sudo apt install git curl docker.io`), and Python 3.10/3.11 (`python3 --version` — Olympe needs 3.9–3.11).
- [ ] **A5. Install Parrot Sphinx** (Parrot's apt repo, per developer.parrot.com/docs/sphinx/installation.html) — do this WITH Claude in a session so we log every step and error.
- [ ] **A6. Sphinx smoke test:** launch the virtual ANAFI Ai in the `empty` world; see it hover. (Claude supplies the exact commands.)

## B. Decisions (10 minutes of thinking, big consequences)

- [x] **B1. Gate G1 — RESOLVED 2026-08-14: greenfield-lean.** Mike's call: build our own governed core; MDS stays a read-only reference (no code copied, license question mooted). Logged in docs 10/FINAL/RESEARCH_LOG.
- [ ] **B2. Teammates + hours.** Confirm who the other two students are and rough weekly hours each, so the roadmap roles (R1/R2/R3) get names.
- [x] **B3. Part 107 plan — RESOLVED 2026-08-14:** Cliff Flock (Part 107 certificated; L3 network engineer at Google) is the identified remote pilot in command for physical flights. Remaining sub-item: confirm his availability for the ~March 2027 test window, and invite him to review the link-loss/security design when it exists (his day job is exactly that).

## C. Week-1 spikes (kill the unknowns first — each ~a day, Claude drives)

- [ ] **C1. Spike-Sphinx (moved up from Feb since you own the laptop):** install Olympe on the laptop, connect to simulated ANAFI Ai (10.202.0.1), take a camera2 photo, download it via olympe.Media. *Pass = the ANAFI stretch path is real.*
- [ ] **C2. Spike-1 (PX4 side):** start SITL with the ready-made image `jonasvautherin/px4-gazebo-headless:1.17.0` (Apache-2.0, one docker run); grab a camera frame → JPEG. Note: gz Python bindings are apt-only (no pip) — plan A is `python3-gz-transport13` on the laptop; plan B is the image's built-in RTSP stream via OpenCV (works from Macs too).
- [ ] **C3. Spike-2 (LLM side):** PydanticAI turns 5 canned photo requests into schema-valid MissionPlans (runs on your Mac; needs an API key or local Ollama). Eval harness decided: pydantic-evals + our validator as scorer; TrustSafeAI's 408 drone-safety prompts join the evil-requests set later.
- [ ] **C4. (OPTIONAL — learning only, since G1 is decided):** reproduce MDS's single-drone SITL demo once, read-only (their `docs/guides/sitl-comprehensive.md`) — worth a half-day for intuition; skip if time is tight.

## D. Project scaffold (after B1 is decided)

- [ ] **D1.** Commit the root repo for the first time (CLAUDE.md, master prompt, docs/, research/, this TODO) + `.gitignore` for `.DS_Store`/`Icon?`/`.env`.
- [ ] **D2.** Create the integration repo skeleton per `docs/architecture-research/08 §2` (core/ backends/ planner/ server/ ui/ tests/).
- [x] **D3. ✅ SAFETY CORE COMPLETE — all 5 waves shipped 2026-08-14, 122 passing tests.** `drone-mission/core/` now holds: the MissionPlan schema (closed vocabulary, plan hash), 15 deterministic rules across 5 waves (shape → envelopes → boundary geometry → live drone state → gates), the DroneBackend contract, the approval service (hash-bound, 300 s TTL, refuses static-only reports, typed "I AUTHORIZE REAL FLIGHT" phrase for physical aircraft), the pre-dispatch gate that re-checks reality before every command, and a manual circuit breaker that beats everything and only a named human can reset. ~20 evil scenarios all die on the exact right rules (incl. approve-then-edit, dead-battery launch, sim-config-to-real-drone, breaker-open). Run: `cd drone-mission && pip install -e ".[dev]" && pytest -q` → 122 passed.
- [x] **D4. ✅ EXECUTOR SHIPPED 2026-08-14 — M1 functionally complete, 134 tests.** An approved mission now *flies* end-to-end on the deterministic fake drone: `core/events.py` (append-only SQLite audit log, gapless replay), `core/engine/machine.py` (13-state mission state machine — illegal jumps are impossible), `core/engine/executor.py` (dispatch gate before every step, telemetry-evidence-gated progress, abort that cancels a hung command mid-await + flies RTH+land, deterministic failsafe recovery, manual-override terminality, idempotent bounded retries, portable waypoint-ring orbit with capture angles), `backends/fake/` (scriptable faults: hangs, timeouts, battery crashes, stick input). Proven in tests: battery crash mid-flight → failsafe RTH; abort preempts a hung goto; retries reuse the same idempotency key; the event log alone reconstructs the whole mission. Two real bugs were caught by the tests and fixed (orbit seam double-photo; idempotency marking failed attempts as done).
- [x] **D5. ✅ LLM PLANNER SHIPPED 2026-08-14 — 140 tests.** `planner/` turns natural language into validated MissionPlans: the model's output type can ONLY contain steps+summary (mission id/boundary/limits are injected server-side — the LLM physically cannot touch the envelope); failed validations feed the exact rule violations back for ≤2 repair rounds; hopeless models return a failing report honestly (which Wave-5 approval then refuses); adversarial drafts ("neighbor's yard at max speed") die in the validator, never in the prompt — all proven with scripted FunctionModels, no API key needed in CI. Live demo ready: `export ANTHROPIC_API_KEY=... && python -m planner.demo "photograph this property"`. This was Spike-2 → real code; M2's language half is done.
- [ ] **D6 (next): PX4Backend (MAVSDK)** — the same missions fly in Gazebo physics: docker SITL bring-up (uses the laptop or any Docker machine), contract-test suite passes on Fake AND PX4, then the M3 demo mission with the gz camera frame-grab (Spike-1). This is where your Linux laptop or Docker Desktop enters the build.

---

**Right now, in order: A1 → A2 → A3, then tell Claude your B1 answer.** Everything else flows from there.

*Log: created 2026-08-14 at start of M0. Update history lives in git once D1 is done.*
