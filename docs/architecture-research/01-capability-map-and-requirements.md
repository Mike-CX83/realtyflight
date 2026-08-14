# 01 — Capability Map and Requirements

**Status:** Phase 1 complete — 2026-08-14. Tier tags: **[MVP]** capstone-committed · **[POST]** near-term post-MVP · **[VISION]** long-term · **[DEFERRED]** explicitly out with rationale.

---

## 1. Capability map by layer

| # | Layer | Capability | Tier | Build vs reuse (see doc 04) |
|---|-------|-----------|------|------------------------------|
| C1 | Operator UI | Web dashboard: request entry, plan review, approval, live telemetry map, mission state, safety events, media gallery | MVP | Build (React+Vite+TS, MapLibre GL, FastAPI WebSocket) |
| C2 | Voice input | Speech→text feeding the same text pipeline | MVP (thin) | Reuse: Web Speech API; faster-whisper offline fallback |
| C3 | Intent interpretation | NL request → typed `MissionPlan` via LLM structured output, bounded action vocabulary, repair loop | MVP | Build thin layer on Pydantic v2 + PydanticAI (provider-neutral incl. Ollama) |
| C4 | Mission representation | Typed `MissionPlan`/`MissionStep` schema: envelope (home, geofence, limits, failsafe policy) + enum primitives, unit-suffixed fields | MVP | Build (informed by QGC .plan, MAVSDK MissionItem, Parrot FlightPlan) |
| C5 | Shot vocabulary | Real-estate shot library: orbit-capture, elevated front/rear angles, nadir/lot, context shot; bracketing spec | MVP core set | Build (domain layer; industry shot lists as spec) |
| C6 | Deterministic validation | Policy engine: schema, geofence (Shapely, local-meters frame), altitude/speed/radius caps, battery reserve, GPS/link health, telemetry freshness, step count, capability checks; deny-by-default; typed violations | MVP | Build (~200 lines, unit-tested); patterns: RoboGuard, MDS Simurgh |
| C7 | Approval workflow | Plain-language mission brief; explicit approve/reject; approval TTL; re-approval on any plan change | MVP | Build (UI + state machine states) |
| C8 | Mission execution | Async state machine: draft→validating→awaiting_approval→approved→executing→(paused/overridden/aborting)→returning→landing→completed/failed; timeouts, retries with idempotency, cancellation that preempts | MVP | Reuse python-statemachine (async) + build monitor |
| C9 | Backend abstraction | `DroneBackend` contract: connect, preflight, takeoff, goto, orbit-or-waypoint-ring, gimbal, capture, RTH, land, hold, abort, telemetry stream, media retrieval | MVP | Build (the architectural centerpiece) |
| C10 | Sim backend #1 | Fake in-process backend for unit tests incl. stale-telemetry/fault scripting | MVP | Build (small) |
| C11 | Sim backend #2 | PX4 SITL + Gazebo Harmonic adapter via MAVSDK-Python (offboard/do_orbit, gimbal v2, gz-topic photo grab) | MVP | Reuse MAVSDK v3 + build adapter |
| C12 | ANAFI backend | Olympe adapter: extended_move_to, camera2 capture/bracketing, gimbal, geofence/RTH config, media download — proven on Sphinx first | Stretch-MVP | Reuse Olympe 8.4 + build adapter |
| C13 | Telemetry & audit | Append-only mission event log (SQLite) + structured JSONL logs; immutable record of request/plan/validation/approval/dispatch/faults/media; replay | MVP | Build small + structlog; Rerun for 3D replay [POST nice-to-have] |
| C14 | Media handling | Capture association to steps, storage, EXIF tagging, MLS-spec JPEG export; HDR merge (Mertens) of brackets | MVP minimal; POST full | Reuse OpenCV/exiftool; build glue |
| C15 | Image QA / retake | Deterministic checks: Laplacian blur, histogram clipping, telemetry tilt gate → retake suggestion | POST | Build small (OpenCV) |
| C16 | Perception | House detection to refine framing (RF-DETR Apache tiers); single-target smoothing (Norfair) | POST | Reuse + fine-tune |
| C17 | Tracking subjects | Person/vehicle follow for walkthroughs | VISION | ANAFI onboard_tracker/auto_look_at or PX4+CV |
| C18 | Indoor autonomy | GPS-denied room-by-room capture | DEFERRED — ANAFI exposes no GPS-denied guided control (Parrot staff, verified); SLAM stacks GPL/dormant; would require new airframe + companion compute | — |
| C19 | Photogrammetry/3D | Ortho/3D property models, splat tours | VISION | ODM/COLMAP/gsplat as side services |
| C20 | Fault injection & tests | Scripted faults in fake backend; PX4 `failure` command (gps/battery/mavlink_signal off…); Sphinx GPS out_of_order/wind/battery params; CI: unit + headless lockstep SITL | MVP | Reuse sim features + build test harness |
| C21 | Security | Localhost-bound control plane; authn/authz + secrets handling before any remotely reachable physical endpoint; sim/real configs visibly distinct | MVP posture, POST hardening | Build config discipline |
| C22 | Property definition | Operator-set property center + boundary polygon on satellite map | MVP | Build (MapLibre draw) |
| C23 | Property auto-discovery | Boundary/center from imagery or GIS (e.g., building footprints) | VISION | Microsoft US Building Footprints (ODbL) candidate |

## 2. Functional requirements (MVP)

FR1. Accept typed natural-language requests; accept dictated speech converted to text (C2) with the final text shown and editable before planning.
FR2. Generate exactly one `MissionPlan` per request using only whitelisted primitives; unknown actions/fields are rejected at parse time (`additionalProperties: false` semantics).
FR3. Primitive set v1: `preflight_check`, `takeoff(alt)`, `goto(waypoint)`, `orbit(center, radius, speed, arc, captures[])`, `set_gimbal(pitch, mode)`, `capture_photo(mode: single|bracket3|bracket5)`, `hold(duration)`, `return_home`, `land`. (Compiled from higher-level shot steps in C5.)
FR4. Validate every plan deterministically (C6) and produce a machine- and human-readable validation report listing every check, pass/fail, and any auto-adjustment.
FR5. Require explicit operator approval after validation; any edit or re-plan invalidates prior approval; approvals expire (TTL) if execution has not started.
FR6. Execute approved missions through `DroneBackend` only; the executor dispatches one validated step at a time and requires telemetry-based completion evidence before advancing.
FR7. Provide live mission state, position on map, altitude/speed, battery, link, GPS status, camera state at ≥2 Hz in the UI.
FR8. Support operator hold, resume, abort, and RTH at any time; abort preempts in-flight steps and transitions through `aborting → returning/landing` deterministically.
FR9. Detect and respond to injected faults: GPS loss, link loss, low battery, command failure/timeout — each with a context-appropriate deterministic response (hold / RTH / land) per the plan's failsafe policy.
FR10. Persist an append-only audit trail sufficient to replay the mission timeline end-to-end; associate every captured image with its mission step.
FR11. Store and display captured media; export JPEGs meeting MLS baseline (sRGB, ≥2048 px long edge).
FR12. Run mission-logic tests headlessly in CI (fake backend) plus at least one scripted SITL integration scenario.

## 3. Non-functional requirements

NFR1. **Determinism:** identical plan + identical fault script ⇒ identical state trajectory in the fake backend (lockstep tolerated in SITL).
NFR2. **Latency:** request→plan ≤15 s typical; approval→takeoff ≤5 s in sim; abort acknowledgement ≤1 s in the executor.
NFR3. **Portability:** mission core is pure Python with zero PX4/Olympe/ROS imports; adapters isolate all vendor SDKs; core runs on macOS + Linux.
NFR4. **Observability:** every state transition and dispatch logged with mission_id/step_id correlation; log format greppable JSONL.
NFR5. **Testability:** validator and state machine 100% unit-testable without any simulator; adapters behind interfaces with contract tests.
NFR6. **Licensing:** distributed core avoids AGPL/GPL/source-available deps (flagged list in 04 §12); attributions maintained.
NFR7. **Reproducibility:** pinned dependencies; documented one-command dev setup per OS; research claims labeled Verified/Claim/Inference with dates.
NFR8. **Explainability:** each rejected plan cites the exact violated rule and value; each mission report reconstructs the causal chain.

## 4. Safety requirements (deterministic, enforced post-LLM)

S1. Geofence: mission boundary polygon + altitude ceiling; every waypoint, orbit annulus, and RTH path checked inside inclusion volume (with buffer) before approval; enforced again at dispatch time.
S2. Numeric envelopes: altitude ∈ [5, 120] m sim default (Part 107's 400 ft ceiling encoded for real ops), speed ≤ configured max (≤8 m/s if ANAFI OA active per vendor doc), orbit radius ∈ [8, 100] m, distance-from-home cap, step count cap.
S3. Battery: preflight minimum %, in-flight reserve trigger → RTH; modeled reserve must cover return distance.
S4. Link/telemetry: staleness threshold (e.g., >2 s ⇒ hold; >10 s ⇒ failsafe per policy); no dispatch on stale state; never substitute synthetic telemetry.
S5. GPS/localization: readiness gate before takeoff (fix type/satellite count in sim terms); loss in flight ⇒ policy response (outdoor default: hold then RTH via backend-native failsafe).
S6. Manual override: stick input / override command immediately suspends autonomous dispatch, cancels queued commands, marks mission `manually_overridden`; resumption only via explicit operator action; on ANAFI, SkyController piloting-source reversion is the mechanism (modal, verified).
S7. Approval: no flight-affecting dispatch without a recorded, unexpired approval bound to the exact plan hash.
S8. Final gate: a circuit breaker immediately before backend dispatch re-checks mode (sim/real), geofence, and kill-switch state; breaker open ⇒ nothing dispatches.
S9. Idempotency + bounded retries: every dispatch carries an idempotency key; retry limits with exponential backoff; timeout ⇒ fault path, never silent continue.
S10. Context-aware failsafes: RTH is not assumed universally safe; failsafe policy is part of the plan envelope (outdoor MVP default: RTH; low-altitude/near-structure: climb-to-safe-alt first — encoded, not improvised). Indoor behavior intentionally unsupported in MVP.
S11. Sim/real separation: physical backend requires a distinct config profile, visual banner, and additional confirmation; sim credentials cannot reach a physical endpoint.
S12. Frames and units validated at every interface boundary (lat/lon vs local ENU vs NED; m vs ft) with typed converters — the classic failure mode named in both the master prompt and MDS/dronesphere audits.

## 5. Supported environments

- **E1 [MVP]:** Simulated outdoor suburban property, GPS available: Gazebo Harmonic world (flat terrain + CC0 house model from Gazebo Fuel + boundary), PX4 SITL x500_gimbal.
- **E2 [Stretch-MVP]:** Sphinx virtual ANAFI Ai in a stock world with a structure (e.g., `dark-forest` house) — validates the Olympe adapter and camera2/media path.
- **E3 [Bounded physical]:** Outdoor private property, daylight, VLOS, Part 107 holder present, manual override armed, conservative envelope subset.
- **Not supported in MVP:** indoor/GPS-denied autonomy (C18 rationale), night ops, over-people ops, BVLOS.

## 6. The vertical slice (build order inside the MVP)

V1. `MissionPlan` schema + validator + unit tests (no UI, no sim).
V2. Fake backend + state machine executing a hardcoded plan; abort/fault unit tests.
V3. LLM structured-output planning with repair loop → same pipeline (text in, validated plan out).
V4. PX4 SITL adapter: takeoff/goto/RTH in Gazebo; then orbit; then gimbal + gz-topic photo capture.
V5. FastAPI + dashboard: request→review→approve→watch; audit log + replay.
V6. Fault-injection demo suite (scripted) + CI wiring.
V7. (Stretch) Olympe adapter against Sphinx; camera2 captures + media download.
Each slice is demonstrable on its own; V1–V6 constitute the committed MVP demo.

## 7. Assumptions to validate early (feed doc 10)

A1. One Ubuntu x86_64 machine (NVIDIA GPU for Sphinx) is obtainable by ~week 6 (Gate G2). PX4 SITL/Gazebo runs headless in Docker/VM meanwhile.
A2. Photo capture from Gazebo via gz-transport Python works at needed fidelity (verified pattern exists; spike in V4).
A3. Sphinx firmware-in-the-loop supports camera2 photo capture + Olympe media download in-sim (agent-verified plausible, OPEN QUESTION — week-1 spike on the Linux box).
A4. LLM structured output reliably emits valid plans with ≤1 repair round for the bounded vocabulary (spike in V3; local fallback via Ollama structured outputs).
A5. Team availability ~10–15 h/wk each holds through spring.
