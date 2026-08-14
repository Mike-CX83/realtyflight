# 10 — Risk Register and Decision Gates

**Status:** v1.1 — updated 2026-08-14 after Phases 6–7. G1/G2 now carry formal recommendations in FINAL_RECOMMENDATION §5 (greenfield-lean; borrow-then-buy-used box) awaiting Mike's sign-off. **R10 downgraded to CLOSED:** iCloud contents materialized; all five local commits pinned (doc 02 §2); local MDS confirmed to contain Simurgh. Re-score monthly. Scoring: Likelihood × Impact, H/M/L.

---

## 1. Decision gates (require Mike's explicit call; nothing proceeds silently)

**G1 — Foundation strategy: RESOLVED 2026-08-14 — Mike chose (b) GREENFIELD-LEAN.**
Decision (Mike's explicit call, satisfying the CLAUDE.md ask-first rule): build our own governed core (~2.5–6 kLOC) on MIT/Apache/BSD dependencies; **MDS/Simurgh is a read-only architectural reference and pattern source — no MDS code enters our repo**, which also moots the PolyForm license question for the distributed codebase (courtesy citation in the report). Rejected alternative (a) adopt-MDS-chassis is recorded with its trade-offs in docs 03 §1 / FINAL §5 for the defense narrative. Consequence: TODO C4 (reproduce the MDS SITL demo) is now **optional learning, not a decision input**. Evidence basis: docs 03 §1, 04 §1, 11 (safety-core build plan), Round-2 finds that shrank the greenfield delta (04-DELTA).

**G2 — Linux machine: RESOLVED at $0 (2026-08-14).**
Mike already owns a qualifying machine: **custom Clevo/Sager NH58AF gaming laptop — AMD Ryzen 7 3800XT (8c), NVIDIA GeForce RTX 2070 Mobile, 32 GB DDR4, 2 TB SanDisk SSD, dual-boot Windows 11 Home + Linux** (upgraded CPU/RAM/storage; OEM keyboard replaced). Against Sphinx requirements: GPU = the exact recommended tier (RTX 2070, 8 GB); CPU meets the 8-core minimum (12-core recommended — expect slower renders, fine); RAM/disk exceed recommended. **Two verification items before closing fully (M0 checklist):** (a) the Linux side must be Ubuntu 20.04/22.04/24.04 x86_64 — confirm distro/version, reinstall or add a partition if it's something else; (b) UEFI Secure Boot must be disabled + current NVIDIA proprietary drivers installed. This laptop becomes the SITL/Sphinx/Olympe/drone-WiFi machine; no purchase needed.

**G3 — Custom aircraft (dormant).** Only if triggered per doc 07 §1. Inputs template in 07 §5.

**G4 — Sphinx parity gate (stretch).** Entry to physical prep: the identical MissionPlan passes on Sphinx virtual ANAFI Ai with captures + media download + fault drills.

**G5 — Physical flight authorization.** Preconditions: G4 passed; Part 107 certificate holder present and acting as RPIC — **RPIC identified 2026-08-14: Cliff Flock, Part 107 certificated (also an L3 network engineer at Google — bonus reviewer for the link/security layer); confirm his availability for the ~March 2027 test window and record it here**; private property with owner permission; Remote ID compliant; VLOS; wind limits; manual override rehearsed (piloting-source reversion verified on the ground); conservative envelope (alt ≤ 30 m, radius ≤ 20 m first flights); written flight cards.

**G6 — Any paid service/API commitment** (LLM spend beyond trivial, map tiles at scale, cloud GPU): document need, alternatives, monthly cost before committing.

## 2. Risk register

| ID | Risk | L | I | Mitigation / trigger |
|---|---|---|---|---|
| R1 | **Parrot platform decay** — ANAFI Ai firmware frozen (7.7.1, 2023); consumer line deprioritized; SDK support could narrow | M | H | Backend-neutral core; PX4 exit ramp (G3); pin SDK versions; verified 2026 SDK releases reduce near-term risk |
| R2 | ~~No Linux/NVIDIA machine~~ **CLOSED 2026-08-14** — Mike's Clevo/Sager NH58AF (RTX 2070, 32 GB, dual-boot Linux) covers it; residual: confirm Ubuntu 20/22/24 + Secure Boot off (M0 checklist) | L | L | Verify distro at M0; single-machine dependency noted (laptop failure would stall Sphinx work — acceptable) |
| R3 | **Sphinx in-sim camera/media gap** — camera2 capture or Media download fails in sim ([OQ]) | L-M | H(stretch) | Week-1 spike on box arrival; fallback = frame-grab via sphinx-cli/RTSP as evidence + physical-only media test at G5 |
| R4 | **gz photo capture friction** — MAVLink camera protocol not wired in gz SITL (verified) | H(known) | M | Designed around: gz-topic frame grab in PX4Backend; spike in M0 |
| R5 | **Orbit semantics drift across backends** — DO_ORBIT not a PX4 mission item; no Parrot orbit primitive | H(known) | M | Portable waypoint-ring orbit as canonical form; per-backend fast-paths; contract tests |
| R6 | **LLM plan quality** — invalid/unsafe plans, over-creative outputs | M | M | Enum-constrained schema, additionalProperties:false, repair loop ≤2, validator is the real gate, curated few-shots; local-model fallback via Ollama structured outputs |
| R7 | **Scope creep** (indoor, tracking, swarm, photogrammetry, "general agent") | H | H | Charter exclusions (00 §5); tier tags in 01; gates for any expansion; CLAUDE.md guardrails |
| R8 | **Team throughput / learning curve** (async Python, MAVSDK, sim ops) | M | H | Vertical slices V1–V7 each demoable; MDS demo reproduction as guided onboarding; AI-assisted dev with TDD skills (claude-power-user tooling) |
| R9 | **License contamination** — AGPL (Ultralytics/ODM), GPL (SLAM, exiv2), NC weights (DA-v2 L, pyiqa), unlicensed repos, PolyForm (MDS) | M | M-H | Landmine list (04 §13); dependency review at PR time; G1 resolves MDS posture; NFR6 |
| R10 | **Workspace integrity** — local repos are unpinned iCloud placeholders; MDS local snapshot may predate Simurgh | H(now) | L-M | Pending-1: materialize, record commits, diff vs upstream; re-clone pinned into isolated research/ if stale |
| R11 | **Manual-override misunderstanding on ANAFI** — modal piloting-source semantics differ from blended-RC expectations | M | H(physical) | Ground rehearsal at G5; abort path releases source + relies on auto-reversion; documented in 06 §4 |
| R12 | **Sim-optimism** — behaviors that pass SITL/Sphinx but differ physically (wind, GPS quality, OA quirks) | M | M | Conservative first-flight envelope; fault drills in both sims; physical tests add margin, never new behavior |
| R13 | ~~No Part 107 holder~~ **DOWNGRADED 2026-08-14** — RPIC identified: Cliff Flock (Part 107 certificated); residual = confirm availability for the March 2027 window + backup plan (a team member studies for the ~$175 exam) if schedules clash | L | M(stretch) | Confirm availability at M4 review; Cliff acts as RPIC with final authority per 14 CFR 107.19 during all physical tests |
| R14 | **Single-maintainer dependencies** (PydanticAI fast-moving; python-statemachine; Norfair) | L | L-M | Pin versions; thin wrappers; fallbacks named per layer (04) |
| R15 | **Evidence rot** — 2026 sources go stale mid-project | M | L | RESEARCH_LOG dates every claim; re-verify at gate reviews |

## 3. Failure-mode quick table (deterministic responses — detailed in Phase 6)

| Fault | Sim injection | MVP response (outdoor, policy-driven) |
|---|---|---|
| GPS degraded/lost | PX4 `failure gps off` / Sphinx `out_of_order` | Hold → if not recovered in T, RTH via backend-native failsafe; mission `failed(gps)` |
| Link loss | PX4 `failure mavlink_signal off` / [OQ Sphinx] | Backend-native auto-RTH (ANAFI: rth.set_delay) + executor marks `link_lost`; no dispatch on stale state |
| Battery low | PX4 `failure battery off` / Sphinx capacity params | Reserve threshold → RTH; critical → land |
| Command timeout/failure | Fake backend scripting; retries exhausted | Bounded retries (idempotent) → hold → operator decision or failsafe |
| Manual override | RC/piloting-source event | Suspend dispatch, cancel queue, state `manually_overridden`; resume only by explicit operator action |
| Operator abort | UI action | Preempt current step → `aborting` → RTH/land per policy |
| Validator/CB open | — | Nothing dispatches; visible reason |

## 4. What evidence would change the architecture

- Sphinx spikes failing (→ re-weigh ANAFI stretch vs PX4-only, G3 inputs).
- PydanticAI/structured-output reliability below threshold in V3 (→ Instructor / grammar-constrained local models).
- MDS local snapshot diverging materially from audited upstream (→ re-audit before G1).
- Part 108 finalization or FAA guidance shifts (→ Tier-3 framing only, no MVP impact).
