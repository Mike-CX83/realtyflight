# 00 — Project Charter and Scope

**Project:** AI Autonomous Real Estate Photography Drone (capstone)
**Owner:** Mike Hankins, Atlas School (Tulsa, OK) — three-person student team
**Timeline:** ~9–10 months from August 2026 (target demonstration: spring 2027)
**Status of this document:** Phase 1 complete — 2026-08-14
**Owned hardware:** Parrot ANAFI Ai (assembled, unflown with custom software) + SkyController 4
**Dev machines:** macOS (Apple Silicon MacBook Air) **plus Mike's Clevo/Sager NH58AF gaming laptop — Ryzen 7 3800XT (8c), RTX 2070 Mobile, 32 GB DDR4, 2 TB SSD, dual-boot Windows 11 + Linux** — which satisfies the Linux/NVIDIA requirement (G2 resolved; see §7)

---

## 1. Problem statement

Real-estate agents and photographers want professional aerial photo packages without learning flight programming or manual cinematography. Today that requires a skilled Part 107 pilot flying manually. The project builds a **governed autonomous photography system**: a user states a desired result in ordinary language ("orbit the house and give me a full exterior package"), and the system converts that intent into a **typed, deterministic, human-approved, monitored mission** that a drone executes safely.

The product goal is explicitly *not* "an LLM connected to a drone." The LLM is a **mission interpreter and planner** operating over a bounded vocabulary. Deterministic code validates; a human approves; a state machine executes; every step is audited.

## 2. Vision tiers

### Tier 1 — Ten-month capstone MVP (committed)
One simulated drone completes one exterior property-photography mission end-to-end:

1. Operator types (or speaks) a bounded real-estate photography request.
2. LLM produces a typed, schema-valid `MissionPlan` composed only of supported primitives.
3. Deterministic validation (geofence, altitude, speed, battery, GPS readiness, telemetry freshness, step limits, camera state) passes, adjusts, or rejects.
4. The UI explains the mission in plain language; the operator approves or rejects.
5. A mission state machine executes it in simulation through a `DroneBackend` adapter: takeoff → positioning → orbit with structure framing → photo captures (including bracketing) → return-to-home → land.
6. Live dashboard shows mission state, telemetry, camera state, safety events.
7. Captured images are associated with mission steps (completion evidence).
8. Hold, abort, manual override, link loss, GPS loss, and low battery behaviors are demonstrated (fault injection).
9. Everything — request, plan, validation results, approval, dispatches, telemetry, faults, media, outcome — is stored in replayable logs.

**Stretch within capstone:** the same backend-neutral mission runs against Parrot Sphinx (virtual ANAFI Ai), then a bounded, manually-supervised physical ANAFI Ai flight.

### Tier 2 — Near-term post-MVP (candidate, not committed)
Voice-first UX polish; house-detection-assisted framing (license-safe detector); deterministic image-quality checks driving auto-retake; richer shot library (elevation passes, roof pass, context shots at multiple altitudes); RAW/DNG + HDR merge pipeline; media export packaging to MLS specs; second physical backend (PX4 aircraft).

### Tier 3 — Long-term commercial vision (context only)
Full exterior+interior packages, subject tracking/walkthroughs, semantic scene understanding, photogrammetry/3D tours, automated editing, shot-quality scoring, multi-property workflows. **Interior autonomy is out of MVP scope on evidence** (see 06 §6 and 04 §9: the ANAFI Ai exposes no GPS-denied guided control — Parrot staff statement — and the credible SLAM stacks are GPL-3.0 and/or dormant). U.S. commercial operation legally requires a certificated remote pilot in command regardless of autonomy level (14 CFR 107.19), which the architecture's human-approval gate mirrors.

## 3. Guiding principles (non-negotiable)

1. **The LLM never flies the aircraft.** It emits a typed `MissionPlan` only. No motor, actuator, rate, or unconstrained movement outputs. Deterministic code re-validates everything after the LLM and before dispatch.
2. **Simulation-first.** No autonomous behavior makes its first appearance on physical hardware. Progression: fake backend (unit tests) → PX4 SITL/Gazebo → Parrot Sphinx (virtual ANAFI Ai) → bounded physical tests with manual override.
3. **Human approval and manual override always.** Approval gates every flight-affecting plan; manual pilot control preempts autonomy; abort must cancel active work, not set a flag.
4. **Backend-neutral core.** Missions, policies, safety results, state, and photography concepts are defined in our own typed domain layer — never in PX4/MAVSDK/ROS2/Olympe types. Adapters translate.
5. **Deny by default.** Missing, stale, invented, or invalid state fails closed. No fake telemetry, ever.
6. **Open-source-first with adoption criteria.** Prefer maintained, documented, license-compatible components; reimplement behind clean interfaces when adoption would import excessive dependencies or license conflicts.
7. **Safety, observability, testability, licensing, reproducibility are architectural requirements**, not final-stage additions.
8. **Explainability.** Every flight-affecting action traces to: operator request → typed plan step → passed policy checks → explicit approval → dispatch → completion evidence. Mike must be able to explain and defend every layer.

## 4. Success criteria for the capstone demonstration

- A non-team-member operator can request, review, approve, and watch a mission succeed in simulation without touching code.
- A deliberately unsafe request (altitude/geofence/battery violation) is visibly rejected or corrected by the validator — not by the LLM prompt.
- Mid-mission abort, hold, manual override, GPS-loss, link-loss, and low-battery injections each produce the designed deterministic response.
- Captured images exist on disk, tied to mission steps; the mission replays from logs.
- Test suite: unit tests on schema/validator/state machine + at least one headless SITL integration test in CI.
- (Stretch) The same mission JSON executes on Sphinx/virtual ANAFI Ai; (stretch) bounded physical flight.

## 5. Explicit exclusions

Drone racing; Atlas team planning; swarm/multi-drone operations; drone shows; general-purpose agent platforms; autonomous indoor/GPS-denied flight (deferred with evidence); BVLOS or unattended commercial operation; automated property-boundary discovery (MVP uses an operator-confirmed property center + boundary); commercial SaaS build-out.

## 6. Regulatory context (verified 2026-08-14)

- **Part 107** governs U.S. commercial ops: certificated remote pilot in command (RPIC) who is "directly responsible for and is the final authority as to the operation" and must retain "the ability to direct the small unmanned aircraft" (14 CFR 107.19); ≤400 ft AGL (plus 400-ft-radius-of-structure exception useful for roof shots, 14 CFR 107.51); VLOS; Remote ID. Autonomy does not shift accountability — our approval + override architecture is the software shape of this rule.
- **Part 108 (BVLOS)** is still an NPRM (published 2025-08-07; comments closed 2026-02-11; final rule expected late 2026/2027) — no product dependence on it.
- Simulation work has no regulatory footprint. Physical tests require a Part 107 certificate holder (decision gate G5 in doc 10), private property with owner permission, Remote ID compliance, and VLOS.

## 7. Constraints and standing assumptions

- **Team capacity:** 3 students, part-time (~10–15 h/wk each assumed), early-intermediate implementation experience, strong systems thinking, AI-assisted development workflow.
- **Hardware constraint (verified, now covered):** Parrot Olympe is Linux x86_64-only (PyPI wheel `manylinux_2_31_x86_64`, Python 3.9–3.11) and Parrot Sphinx requires Ubuntu 20.04/22.04/24.04 with an NVIDIA GPU (RTX 2070+ recommended) and Secure Boot disabled — neither runs on MacBooks, and PX4 SITL + Gazebo has no native Apple Silicon path. **Covered by Mike's Clevo/Sager NH58AF (RTX 2070 Mobile = the recommended Sphinx GPU; 8-core Ryzen meets minimum; 32 GB/2 TB exceed recommended; dual-boot Linux).** G2 resolved at $0; residual M0 checks: Linux side must be Ubuntu 20/22/24, Secure Boot off, current NVIDIA drivers (10 §G2).
- **Budget:** $0 committed. Any purchase (Linux box, cloud GPU, future PX4 aircraft) passes through a decision gate with need, alternatives, and cost documented.
- **LLM access:** provider-neutral design; cloud API keys (low cost) and/or local models via Ollama. The mission record stores final *text*, keeping STT and LLM providers swappable and outside the safety chain.
- **Licensing posture:** capstone code aims for MIT/Apache-compatible dependencies in the distributed core; source-available or copyleft components require explicit sign-off (10 §G1) or isolation behind services.
- **Workspace integrity (current blocker):** the five collected repos on Mike's Mac are iCloud placeholders (contents not downloaded) — local audit pends materialization; upstream audit already completed from GitHub (docs 02/03).

## 8. Representative first mission (baseline, refined by research)

> "Photograph this property: orbit the house at a safe radius and altitude, keep the camera on the structure, capture 8 exterior photos plus 1 overhead lot shot, then return home."

Compiles to: preflight checks → takeoff to validated altitude (~25 m sim) → transit to orbit join point (smooth entry, not a teleport) → orbit of validated radius with heading/gimbal locked on structure center → 8 captures at 45° spacing (3-frame bracket at each per industry HDR practice) → climb to nadir position → 1 overhead capture → RTH → land → media associated to steps → mission report. Industry practice validates the shot pattern: elevated front 3/4 at 50–80 ft AGL, rear, top-down lot/nadir, context shots, orbit — a finite, geometric shot list requiring **no computer vision for the MVP** (see 04 §10).

## 9. Deliverables of the research phase

Documents 00–10, RESEARCH_LOG.md, and FINAL_RECOMMENDATION.md in this folder, culminating in: decisive architecture, technology stack with fallbacks, MVP definition, ten-month roadmap, risk register with decision gates, and the disposition of every collected repository.
