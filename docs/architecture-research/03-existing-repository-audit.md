# 03 — Existing Repository Audit

**Status:** v1.0 — upstream audit complete; **local snapshots pinned and spot-verified against the audit (2026-08-14, post-materialization)**. Pinned commits in doc 02 §2. Local confirmations: `dronesphere/agent/validator.py` and both test files are **0 bytes on disk** and no LICENSE file exists locally ✔; `LLM-controlled-drone` has no local LICENSE ✔ and the four audited source files are present ✔; `FPV-Drone-AI-Agent` `MissionTypes.hpp`/`RuleEngine.cpp` present ✔; **local MDS (`30899be`, cloned ~2026-08-11) contains the full Simurgh layer** (agent_policy/agent_tools/agent_runtime/tests/guide) ✔ — the audit below describes the code Mike actually has.
**Method & evidence standard:** since local contents are unreadable (doc 02 §3), each repo was audited at its **upstream HEAD on GitHub, 2026-08-14**, by reading actual source files, LICENSE files, manifests, tests, and docs (not READMEs alone), via a dedicated research agent whose full source list is in RESEARCH_LOG.md. Labels: **[Verified]** read in the cited file; **[Repo claim]** stated by docs, unconfirmed; **[Inference]** reasoned. Caveat: local snapshots may be older than what is described here.

---

## 1. `mavsdk_drone_show` → alireza787b/mavsdk_drone_show ("MDS") — Foundation candidate

**Scale:** 4,064 commits, 3 contributors, Python ~59% / JS ~26%; multi-service: drone-side runtime, FastAPI GCS backend (FastAPI 0.115 + Pydantic 2.10), React dashboard, SITL tooling, plus drone-show / Smart-Swarm / SAR subsystems that are dead weight for a one-drone capstone. [Verified: repo, requirements.txt]

**License:** PolyForm Noncommercial 1.0.0 (free for students; attribution mandatory) / PolyForm Small Business + <10-drone cap / negotiated commercial. Source-available, **not** OSI open source; derivatives inherit restrictions. Spot-verified directly from the LICENSE files by the lead session. [Verified]

**The relevant subsystem — "Simurgh Operator" (governed AI layer, v5.5 era, 2026):**
- Deny-by-default policy: `config/agent_policy.yaml` — risk classes (observe→destructive), runtime modes (read_only/sitl/real), `always_confirm_before_action: true`, circuit breaker enabled, `unknown_tool_policy: deny`, 300 s approval TTL. [Verified]
- Typed tool registry: `config/agent_tools.yaml` (4,711 lines), per-tool JSON Schema with `additionalProperties: false`, risk class, runtime modes, side-effects. The **only** guarded flight tool `mds.flight.command.execute` accepts exactly TAKE_OFF / LAND / RETURN_RTL / PRECISION_MOVE and `requires_approval: true`; raw command submission is never model-exposed. [Verified]
- Runtime: `gcs-server/agent_runtime/{policy,audit,sessions,language,answer_composer}.py`. [Verified: files exist and read]
- LLM boundary: provider-neutral; optional OpenAI adapter used for interpretation only; deterministic offline fallback parser; provider rewrites that alter parsed numeric values are discarded. [Verified: docs/guides/simurgh-operator.md]
- Completion evidence: telemetry-verified landing (altitude/vspeed/home-distance thresholds), not command-ack trust; idempotency keys on movement commands. [Verified: same guide]
- Tests: `tests/test_agent_runtime_foundation.py`, 691 lines / 32 tests, incl. `test_registry_rejects_unsafe_direct_flight_tool`. [Verified]
- Demonstrated single-vehicle SITL run 2026-07-27 (takeoff→move→RTL with ULog evidence), explicitly labeled beta. [Verified: checkpoint doc; note some retest evidence lives in a private mirror — Repo claim]

**Gaps for our capstone:** no orbit primitive, no gimbal control, no camera/photo/media pipeline, no photography domain layer, PX4-only (no Olympe), no backend-neutral mission core (concepts are MDS-shaped). Lab profile ships with auth off on trusted networks (README warns). [Verified]

**Verdict: Foundation candidate** — the only collected repo whose governance chain (typed tools → policy → approval → circuit breaker → monitored execution → audit → tests) is verified in code, tests, and a SITL demo. Two adoption strategies go to **Gate G1** (doc 10): (a) use MDS as the chassis and extend; (b) build a lean greenfield core and use MDS as the reference implementation + SITL tooling donor. Preliminary recommendation and trade-offs: FINAL_RECOMMENDATION (pending), summarized in doc 10 §G1. Either way: reproduce its SITL demo early (CLAUDE.md progression step 2), and Mike must explicitly accept the PolyForm terms before it becomes distributed foundation code.

**Study first:** `config/agent_policy.yaml`; `config/agent_tools.yaml` (`mds.flight.command.execute`); `gcs-server/agent_runtime/`; `tests/test_agent_runtime_foundation.py`; `docs/guides/simurgh-operator.md`; `docs/guides/sitl-comprehensive.md`.

## 2. `dronesphere` → alireza787b/dronesphere — Concepts donor; as a system: unsafe/misleading

**Scale:** ~101 files, 4-service NL-drone stack (drone-side FastAPI `agent/`, `server/`, FastMCP `mcp-server/`, `llm-bridge/` demo). Dormant since 2025-09-30. **No LICENSE file** despite README's "MIT License - See LICENSE file" — all-rights-reserved by default. [Verified]

**Confirmed the prior hypothesis ("overstates safety"):**
- `agent/validator.py` is a **0-byte file**; `tests/test_basic.py` and `tests/test_integration.py` are **0-byte files** — while the README advertises "AI-Enhanced Safety… traditional safety checks" and a testing infrastructure. [Verified: raw fetches return empty 200s]
- Validation that does exist: per-command `jsonschema` Draft-7 checks + parameter bounds in `agent/commands/goto.py` (alt −500..10000 m, speed ≤20 m/s). **No geofence, battery, distance-from-home, or telemetry-freshness policy anywhere.** [Verified]
- On LLM timeout the MCP layer **silently falls back to a keyword/regex parser that still emits flight commands** (`mcp-server/core/llm_handler.py`) — an instructive anti-pattern for our "no degraded-mode command generation" rule. [Verified]
- No approval flow, no auth on the agent API, no abort endpoint; executor logs "Continuing despite validation failure" for non-critical steps. [Verified: agent/api.py, agent/executor.py]

**Worth learning (reimplement, don't copy — no license):** `mcp-server/tools_navigation_enhanced.py` (`smart_navigate` unifying GPS/NED/offset/body frames via pymap3d), the four coordinate-frame transform tools, YAML-schema-per-command registry pattern. These concepts already live on, governed, in MDS by the same author.

**Verdict: Reusable component donor (concepts only) / unsafe-misleading as a system.** Keep read-only for reference.

## 3. `LLM-controlled-drone` → pratikPhadte/LLM-controlled-drone — Research example only

**Scale:** one ROS2 Jazzy package, ~1,130 LOC Python (4 files) + px4_msgs submodule + Gazebo world. Created 2026-02-25; entire push history ~32 minutes; 79 stars from a YouTube demo; 22 unanswered issues; README admits "this code was also generated by LLM." **No LICENSE file.** [Verified]

**Architecture (the anti-pattern our validator exists to prevent):** system prompt literally assigns the LLM the role "You are the autonomous flight controller for a PX4 drone," asks it to do GPS→NED arithmetic in-token, and `command_translator.py` maps the LLM's free-form JSON **directly to PX4 trajectory setpoints with no clamping, no geofence, no altitude enforcement** (limits exist only as prompt text). LLM can arm the vehicle. No tests, no state machine, no approval. [Verified: llm_client.py, command_translator.py]

**Residual value:** `brain_node.py` is a compact, current reference for ROS2↔PX4 offboard wiring (`/fmu/in/trajectory_setpoint`, `OffboardControlMode`, `VehicleCommand` arming) if a ROS2 path is ever revisited; the YOLO-detections-into-planner-context loop is a neat later idea. 30 minutes of reading, no reuse.

**Verdict: Research example only.**

## 4. `FPV-Drone-AI-Agent` → ai-in-pm/FPV-Drone-AI-Agent — Architectural reference only

**Scale:** C++20/CMake, Windows-first, ~70 source files; targets a real EMAX Nanohawk over Betaflight MSP; **no simulator at all**; "tests" = one 29-line smoke main(). Repo created and abandoned within ~4 hours on 2026-03-08 by an account that mass-produces AI-generated demo repos. [Verified + Inference]

**License:** README §License: `Currently "Closed License"` + a generated RAIL-AMS document; **and** it vendors Betaflight GPL-3.0 MSP headers — internally conflicted; treat as look-don't-copy (confirms the prior hypothesis). [Verified]

**Why it still matters:** it is a textbook one-page miniature of our exact pipeline — `prompt → JsonPlanParser → typed MissionPlan (requiresOperatorAuthorize) → RuleEngine deterministic deny-with-reason (battery ≥30%, link health, geofence, altitude cap, per-move distance budget) → executor → MSP client → layered failsafes with manual-TX priority`. `include/planning/MissionTypes.hpp` and `src/safety/RuleEngine.cpp` are worth imitating when designing our Python domain types. [Verified]

**Verdict: Architectural reference only.**

## 5. `claude-power-user` → Hacker0x01/claude-power-user (fork of obra/superpowers) — Out of scope; keep as tooling

MIT-licensed Claude Code skills library (TDD, debugging, planning, subagent workflows). Not drone software; excluded from the architecture matrix. Useful for how the team builds; consider pointing at the actively maintained upstream `obra/superpowers` instead of the 2-star fork. [Verified]

---

## 6. Safety comparison across the four drone repos (the capstone's core axis)

| Control | MDS/Simurgh | dronesphere | LLM-controlled-drone | FPV-Drone-AI-Agent |
|---|---|---|---|---|
| Typed/schema'd LLM output | Yes — registry JSON Schema, additionalProperties:false [V] | Partial — jsonschema per command; substring JSON extraction [V] | No — free-form JSON, prompt-only rules [V] | Yes — typed MissionPlan [V] |
| Deterministic post-LLM policy | Yes — deny-by-default policy engine [V] | **validator.py empty**; only param bounds [V] | **None** [V] | Yes — RuleEngine, hardcoded toy limits [V] |
| Human approval gate | Yes — always_confirm + approval broker + TTL [V] | None [V] | None [V] | Authorization flag check [V] |
| Final circuit breaker | Yes [V] | None | None | Disarm failsafes (unverifiable in flight) [V code] |
| Completion evidence | Telemetry-verified (thresholds) [V] | Command results only | None | None |
| Tests of the above | 691-line suite, 32 tests [V] | **Test files empty** [V] | None | 29-line smoke [V] |
| Degraded-LLM behavior | Deterministic fallback can't exceed typed draft; numeric rewrites discarded [V] | **Keyword fallback still issues flight commands** [V] | n/a — LLM is the controller | Returns idle JSON [Repo claim] |

## 7. Cross-repository provenance table (capability → best source)

| Needed capability | Best source | Files/symbols | Reuse method | License note |
|---|---|---|---|---|
| Governed AI/operator architecture | MDS Simurgh | agent_policy.yaml, agent_tools.yaml, agent_runtime/ | Adopt chassis **or** study-and-reimplement (Gate G1) | PolyForm — sign-off needed if distributed |
| Typed tool/action registry pattern | MDS | agent_tools.yaml schema style | Pattern reuse | Pattern only — uncopyrightable ideas |
| Policy engine + circuit breaker | MDS (real), FPV agent (miniature) | policy.py; RuleEngine.cpp | Study both; write our own ~200-line engine | Ours = MIT |
| Human confirmation + audit | MDS | approval broker, audit.py | Pattern reuse or adopt | — |
| PX4 SITL setup + tooling | MDS | sitl guides, mds.sitl.instances | Reuse workflows | — |
| MAVSDK flight adapter | MDS (guarded execute), MAVSDK docs | command tracker | Reference for our PX4Backend | — |
| NL relative-nav + frame conversion | dronesphere | tools_navigation_enhanced.py, tools.py | **Reimplement** (no license) | unlicensed |
| ROS2/PX4 offboard wiring reference | LLM-controlled-drone | brain_node.py | Read-only reference | unlicensed |
| prompt→typed plan→veto miniature | FPV-Drone-AI-Agent | MissionTypes.hpp, RuleEngine.cpp | Read-only reference | closed |
| YOLO/vision loop | LLM-controlled-drone | yolo_detector.py | Concept only (post-MVP uses license-safe detector) | AGPL risk in ultralytics |
| Orbit/path generation | **none of the five** | — | Build (~100 lines, doc 04 §11) | — |
| Camera/gimbal/media control | **none of the five** | — | Build on MAVSDK/Olympe APIs | — |
| Real-estate shot planning | **none of the five** | — | Build (domain layer) | — |

**Bottom line:** the collected set contains exactly one serious chassis (MDS/Simurgh), one cautionary tale that validates our safety thesis (dronesphere), two teaching examples, and one dev-tooling library. The capstone's genuinely new work — photography mission layer, orbit/gimbal/camera primitives, backend-neutral core, Olympe adapter — exists in **none** of them, which is consistent with the external landscape scan (doc 04): our differentiator is real.

## 8. Pending items — updated 2026-08-14

- **Pending-1 ✔ resolved** (see Status header and doc 02 §2): dispositions in §1–§5 are final for the research phase.
- Reproduce the MDS single-drone SITL demo in an isolated environment (progression step 2) — scheduled as roadmap M0, not performed during document-phase research.
