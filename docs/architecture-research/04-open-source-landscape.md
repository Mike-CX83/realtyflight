# 04 — Open-Source Landscape (Candidate Catalog by Layer)

**Status:** v1.0 initial sweep complete — 2026-08-14. Saturation per category noted in §13; the sweep ran as four parallel evidence-gathering agents whose full source lists (every URL, all accessed 2026-08-14) are archived in RESEARCH_LOG.md. Licenses were read from actual LICENSE files / registry metadata, releases from GitHub/PyPI/npm. Labels: **[V]** verified against primary source · **[C]** vendor/repo claim · **[I]** inference. Verdicts: **adopt** (use as dependency) · **adapt** (use with modification) · **pattern** (study & reimplement) · **reference** (read-only) · **reject** · **defer**.

---

## 1. Existing LLM-drone projects (12+ examined — none provides our full chain)

| Project | License / activity | What it is | Verdict |
|---|---|---|---|
| **AUSPEX** (UniBw München) — github.com/UniBwM-IFS-AILab/AUSPEX | MIT; active into 2026-05; Frontiers Robotics & AI paper 2025-08 [V] | Modular UAV decision framework; "Say'n'Fly" **LLM-modulo** planner: LLM proposes, external verifier checks | **pattern** — the academic twin of our thesis; cite in defense; too swarm/ROS2-heavy to adopt |
| **RoboGuard** (KumarRobotics/UPenn) | MIT; small research artifact (4 commits) [V] | LTL safety specs checked against LLM-proposed robot plans pre-execution | **pattern** — strongest OSS precedent for a deterministic safety gate over LLM plans |
| **TypeFly** (typefly/TypeFly, IEEE TMC 2025) | Apache-2.0 (raw LICENSE; sidebar shows GPL elsewhere — raw file authoritative); no releases; 243 commits [V] | NL → "MiniSpec" closed DSL over fixed skills; Tello + Go2 | **pattern** — closed action vocabulary + tiny grammar idea; runtime not reusable |
| **PromptCraft-Robotics** (Microsoft) | MIT; dormant since 2023; AirSim dead [V] | ChatGPT emits calls against a small approved function library | **pattern** — the "approved function vocabulary" origin point |
| **MDS / mavsdk_drone_show** | PolyForm NC / SB / commercial; very active (2026-08-13 changelog) [V] | See doc 03 §1 — governed Simurgh Operator | **foundation candidate / adapt** (Gate G1) |
| **UAV-VLA** (sautenich/uav-vla, HRI 2025) | MIT; 149★ [V] | Text + satellite imagery → target locations → waypoint plans | **pattern** — relevant to future property-center discovery; no safety layer |
| **EchoPilot** (Bilalileri, PX4 forum 2025-08) | **no LICENSE** [V]; 20★, 8 commits | Voice → Ollama → LangGraph/MCP → MAVSDK → PX4 | **reference only** — closest stack twin; proves feasibility; license bars reuse; no deterministic gate |
| **DeepDrone** (evangelosmeklis) | GPL-3.0; 194★ [V] | Conversational control via LiteLLM + DroneKit (aging upstream) | **reject** as base; its LiteLLM provider-neutral pattern noted |
| ChatDrones / embodied-drone-agents / MAVLink-AI-Agent / Leviosa | all **no LICENSE**; toy scale [V] | Various ChatGPT→ROS2/MAVSDK translators | **reject** (unlicensed; single-action; no safety) |
| **UAVs_Meet_LLMs** (Hub-Tian) | MIT; 497★; tracks field (Information Fusion 2025 survey) [V] | Curated literature/code index | **adopt as reading map** |

**Finding:** across the whole field, no OSS project implements typed plan → deterministic validation → human approval → audited execution end-to-end; the serious validation work is academic (RoboGuard, Say'n'Fly). Our architecture is confirmed, not pre-empted. [I]

## 2. Structured LLM output (NL → strict MissionPlan JSON)

| Tool | License / release | Verdict |
|---|---|---|
| **Pydantic v2** | MIT; 2.13.x 2026-08 [V] | **adopt** — schema + validators; the type backbone |
| **PydanticAI** | MIT; 2.29.0 2026-08-13 [V] | **adopt (primary)** — model-agnostic (OpenAI/Anthropic/Ollama), typed `output_type`, automatic validation-retry repair loop |
| **Instructor** | MIT; 1.15.4 2026-06 [V] | **fallback** — same idea, lighter |
| **Outlines** (dottxt) | Apache-2.0; 1.3.3 2026-08 [V] | **defer** — grammar-constrained decoding for local models if hard-offline guarantee ever needed |
| llama.cpp GBNF / Ollama structured outputs | MIT; active [V] | **defer/optional** — local-model path (Ollama `format=` schema documented) |
| LangChain/LangGraph | MIT; active [V] | **reject for this step** — see §9 |
| BAML | Apache-2.0; active [V] | **reject** — extra DSL/compiler toolchain without need |
| LiteLLM | MIT; active [V] | **fallback** — provider shim only if not using PydanticAI |

## 3. State machine + durable execution

- **python-statemachine** — MIT; 3.2.1 (2026-08-01); sync+async engines, guards, diagram export. **adopt (primary)** [V]
- **transitions** — MIT; 0.9.3 (2025-07); hierarchical/async. **fallback** [V]
- **Temporal** (temporalio 1.31.0, MIT) — **reject: overkill** (separate server + deterministic-workflow constraints for a single-process, minutes-long mission) [V/I]
- **eventsourcing** (BSD-3; 9.5.4 2026-03) — **reject in favor of ~40 lines of hand-rolled append-only SQLite** `mission_events(mission_id, seq, ts, type, payload_json)` written from state-machine hooks; doubles as the immutable audit log. [V/I]
- XState (MIT, TS) — **reject for backend** (Python executor); optional read-only mirror in UI unnecessary. [V]

## 4. Policy / validation

- **Pydantic validators** (structure) + **pure-Python policy engine** (~200 lines, typed `PolicyViolation`s) + **Shapely** (BSD-3; 2.1.2 2025-09) for geofence geometry — **adopt**. Project lat/lon into a local meters frame before distance math (pymap3d or hand-rolled AEQD) — Shapely is planar. [V/I]
- jsonschema (MIT) — only at a non-Python wire boundary; otherwise redundant. **defer** [V]
- OPA / cerbos (Apache-2.0) — external policy services + DSLs; **reject: overkill**; every rule must be explainable on stage. [V/I]
- guardrails-ai (Apache-2.0) — text/PII-oriented LLM output validation, not robotics; **reject** for the flight gate. [V]

## 5. Mission-plan format precedents (schema inspiration — all **pattern**)

- **MAVLink mission protocol** [V: mavlink.io]: `MISSION_ITEM_INT` (seq, frame, command, params, x/y/z ×1e7), count/request/ack handshake. Lesson: frames and integer scaling are where unit bugs live — validate at boundaries.
- **QGroundControl `.plan` JSON** [V: QGC dev docs]: envelope {mission, geoFence (inclusion/exclusion polygons+circles), rallyPoints}, SimpleItem vs ComplexItem (Survey/CorridorScan/StructureScan). Lesson: our envelope copies geofence+home placement; our high-level shot steps compile down to primitives exactly like ComplexItems.
- **MAVSDK Mission API** [V: MAVSDK-Proto]: `MissionItem` carries per-item gimbal_pitch/yaw, camera_action (TAKE_PHOTO, START_PHOTO_INTERVAL/DISTANCE…), speed, acceptance radius. Lesson: our PX4 adapter can be near-1:1.
- **Orbit reality check** [V: PX4 user guide + MAVSDK proto]: MAVSDK `Action.do_orbit(radius, velocity, yaw_behavior, lat, lon, alt)` exists (yaw default HOLD_FRONT_TO_CIRCLE_CENTER — camera-on-center for free); PX4 Orbit is a **guided-mode command, not a supported mission item** (`MAV_CMD_DO_ORBIT` absent from PX4's mission-command list). Consequence: the executor supervises orbits as guided steps with our own join/exit + capture logic, or compiles waypoint rings + `DO_SET_ROI_LOCATION`. The portable waypoint-ring version is also the only form the Parrot adapter can execute — build it first, use `do_orbit` as a PX4 fast-path.
- **Parrot FlightPlan** [V: developer.parrot.com]: MAVLink *text* file (QGC WPL), FlightPlan V2 closer to standard; ANAFI Ai auto-inserts two start waypoints; frames limited. Lesson: backend-neutral plans must not assume PX4 semantics; community `qgc-mavlink-converter` (mgr098) exists as a reference.
- UgCS / FlytBase (proprietary) [C]: route-level failsafe actions per link/GPS/battery loss — copy the *idea* of an explicit failsafe policy in the plan envelope.

## 6. Telemetry / observability / replay

- **structlog** — MIT/Apache dual; 26.1.0 (2026-06). **adopt** — JSONL logs with mission_id/step_id binding = greppable audit trail. [V]
- **SQLite append-only event store** — stdlib. **adopt** (see §3). [I]
- **Rerun** (rerun-io) — MIT OR Apache-2.0; SDK 0.36.0 (2026-08-10); time-indexed 3D + timeseries, `.rrd` recordings. **adopt (post-flight replay)** — planned-vs-actual 3D flight path + capture events is a killer demo artifact. [V]
- **Foxglove** — OSS Studio repo archived 2024-07-18; v2 proprietary (free tier limits). **reject.** **Lichtblick** (BMW fork, MPL-2.0) — **fallback** only if MCAP/ROS tooling ever matters. [V]
- Grafana (AGPL) / OpenTelemetry — **reject for MVP** (service weight; tracing machinery for a single process). [V/I]

## 7. Dashboard / map

- **React + Vite + TypeScript** — commodity baseline. **adopt.** [I]
- **MapLibre GL JS** — BSD-3; 6.x active 2026. **adopt** (GPU tiles, bearing/pitch suit orbit visualization). Leaflet (BSD-2; 1.9.4 from 2023) — **fallback**. [V]
- Satellite imagery: **Esri World Imagery** free with attribution (terms check before publication) [C]; USGS/NAIP public-domain US imagery covers Tulsa [I]. MapTiler/Mapbox metered free tiers — fallback. [C]
- **FastAPI** (MIT; 0.141.x 2026-07) + uvicorn + native WebSocket at 2–10 Hz. **adopt.** [V]

## 8. Speech-to-text (outside the safety chain — mission record stores final text)

- **Web Speech API** (Chrome) — zero-cost, zero-backend MVP dictation. **adopt (MVP)** [V: MDN]
- **faster-whisper** — MIT; 1.2.1 (2025-10); CTranslate2 alive (4.8.1, 2026-07). **adopt (offline fallback)** [V]
- whisper.cpp — MIT; v1.9.2 (2026-08). **alternative** (C++ friction in a Python backend). [V]
- Moonshine — English models MIT; active 2026. **optional spike** for live-mic latency. [V]
- Vosk — Apache-2.0; PyPI stale (0.3.45, 2022). **reject.** [V]

## 9. Agent framework question — decisive answer: **No.**

Intent→plan is a *pure transformation* (NL + fixed context → one `MissionPlan`), not a long-horizon tool-exploration problem. Everything an agent framework would manage (validation, approval, execution monitoring) lives in *our* deterministic code **by design** — inserting an agent loop between LLM and dispatch blurs exactly the boundary the capstone exists to demonstrate. PydanticAI already provides the two useful features (provider-neutrality, validation-driven retries) in ~20 lines. Field evidence: the LangGraph-based twin (EchoPilot) still lacks a deterministic gate; the rigorous systems (RoboGuard, Say'n'Fly) put intelligence in the *checker*. Escape hatch: a single clarifying round-trip or geocoding tool call fits inside one bounded PydanticAI run. [V/I]

## 10. Real-estate photography domain (industry sources — grounds the shot vocabulary)

- Standard aerial shot list: elevated front 3/4 (declutters ground level), rear/backyard, top-down nadir (lot lines), context/neighborhood shots, orbit; most flattering residential band **50–80 ft AGL** (50–150 usable); low passes 10–20 ft above roofline for detail. Packages: 10–20 edited aerials typical (basic 5–15). [V: Drone Launch Academy; JOUAV guide; Vantage Aerial pricing guide]
- HDR practice: AEB 3–5 frames (pro guidance up to ±4 EV span); hover-stable bracketing; RAW for editing latitude. **ANAFI Ai native bracketing is 3/5/7 frames (±1/±2/±3 EV)** — maps 1:1 to `capture_photo(mode=bracket3|5|7)`. [V: hdrsoft guide; parrot.com camera tech docs]
- Deliverables: MLS minimums ~1024×768, 2026 recommendation 2048×1536, JPEG sRGB, modest file caps ⇒ final deliverables are modest JPEGs; RAW is for editing, not delivery. Golden hour preferred. [V: fotober MLS spec roundup]
- Pricing context (commercial vision): $150–300 basic stills → $450–800 full residential packages. [V: two pricing guides]
- **Conclusion:** the MVP shot list is finite and geometric — encodable as typed mission steps with zero CV. [I]

## 11. Computer vision / imaging (post-MVP; license-vetted)

| Need | Primary | Fallback | Rejected / landmines |
|---|---|---|---|
| Detection (house framing) | **RF-DETR Nano/Small** (Apache tiers only; v1.8.3 2026-06) [V] | RT-DETRv2/v4 (Apache; active) [V] | **Ultralytics YOLO — AGPL-3.0** (viral for the commercial vision; keep out of core) [V]; YOLOX stale; MMDetection maintenance-mode; RF-DETR XL/2XL under restrictive PML [V] |
| Tracking (single target) | **Norfair** (BSD-3; 2.3.0 2025-04) [V] | supervision (MIT) + roboflow `trackers` (license to verify) [V/C] | ByteTrack/BoT-SORT reference repos (MIT but dormant — algorithm reference only); Ultralytics trackers (AGPL) [V] |
| Segmentation | SAM 2.1 (Apache) **defer** [V] | — | SAM 3 custom non-OSI license — review before use [V] |
| Depth | Depth Anything V2 **Small only** (Apache) **defer** [V] | Apple Depth Pro (custom permissive; frozen) [V] | DA-V2 Base/Large/Giant weights are **CC-BY-NC** [V] |
| IQA / retake | **Deterministic trio:** Laplacian blur variance + histogram clipping + telemetry tilt gate (OpenCV/NumPy) [I] | opencv-contrib BRISQUE (model files required); piq (Apache, stable) [V] | **pyiqa — PolyForm Noncommercial** [V] |
| RAW/HDR | MVP: JPEG + native 3-bracket + **OpenCV MergeMertens** fusion; EXIF via **exiftool** subprocess (Artistic/GPL dual — CLI use safe) [V] | rawpy (MIT) / LibRaw (LGPL/CDDL) DNG pipeline when needed [V] | Linking exiv2 (GPL-2); enfuse dep (GPL-2, dormant) [V] |
| Photogrammetry/3D | **defer all**: WebODM/ODM (AGPL — run only as unmodified side service), COLMAP (BSD; 4.0.4 2026-04), Meshroom (MPL-2), gsplat (Apache, active) [V] | — | Embedding AGPL ODM code in product |
| Datasets | Microsoft US Building Footprints (ODbL) for GIS geometry [V] | self-labeled oblique frames from sim + real captures [I] | xView license unclear/NC-flagged — OPEN QUESTION [V/C] |

## 12. GPS-denied VIO/SLAM (evidence for the indoor deferral)

ORB-SLAM3 (GPL-3.0; last release 2021; 540 open issues), VINS-Fusion (GPL-3.0; dormant), OpenVINS (GPL-3.0), Kimera-VIO (BSD; stale 2019) — the battle-tested stacks are GPL and/or dormant; RTAB-Map (BSD; 0.23.1 2025-10; ROS2 binaries) is the only defensible future path and still implies a PX4 airframe + companion computer + months of calibration. **Plus the decisive platform fact: the ANAFI Ai accepts no external position input and exposes no GPS-denied guided control (doc 06 §6).** Verdict: indoor autonomy is a documented next-stage milestone, not an MVP line item; interiors remain manually-piloted in industry practice anyway. [V/I]

## 13. License landmine summary

- **AGPL-3.0:** Ultralytics YOLO, ODM/WebODM, Grafana — fine for an open capstone, poisonous to a closed commercial product; keep out of the distributed core.
- **GPL-3.0/2.0:** ArduPilot (fine to *talk to* over MAVLink; don't link), ORB-SLAM3, VINS-Fusion, OpenVINS, exiv2, enfuse, QGC source.
- **Source-available / NC:** MDS PolyForm (Gate G1), pyiqa PolyForm-NC, DA-V2 large weights CC-BY-NC, RF-DETR XL/2XL PML, SAM 3 custom.
- **Unlicensed (no reuse):** dronesphere, LLM-controlled-drone, EchoPilot, ChatDrones, embodied-drone-agents, Leviosa.
- **Clean core candidates:** MIT/Apache/BSD throughout the recommended stack (Pydantic, PydanticAI, python-statemachine, Shapely, FastAPI, MapLibre, structlog, Rerun, MAVSDK, faster-whisper, OpenCV, rawpy).

## 14. Saturation status per category

| Category | Status | Basis |
|---|---|---|
| LLM-drone projects | **Saturated for decision purposes** — 12+ candidates across academic + hobby space; consistent negative result on full-chain governance | multiple query families incl. arXiv surveys; new finds converged on same patterns |
| Structured output | **Saturated** — mature, well-known field | registry-verified versions |
| State machine / durable exec | **Saturated** | ditto |
| Policy/validation | **Saturated** for our scale (custom engine decision stable) | precedents identified |
| Mission formats | **Saturated** — canonical sources (MAVLink/QGC/MAVSDK/Parrot) all read | primary specs |
| Observability | **Saturated** — Foxglove licensing resolved; Rerun verified | primary sources |
| Dashboard/STT | **Saturated** | registries + MDN |
| CV/detection/tracking/depth | **Adequate for post-MVP planning**; revisit at post-MVP kickoff (fast-moving field) | licenses verified now |
| Photogrammetry/SLAM | **Saturated for the deferral decision** | licenses + activity verified |
| Cinematography research code | **Adequate** — CineMPC (no license found), CMU JFR2020 (no code release found), AirCap (GPL, dormant) — all reference-only; 2025-2026 LLM-cinematography papers tracked as leads | OPEN leads logged |
| Simulators | see doc 05 (saturated) | — |
| Parrot ecosystem | see doc 06 (saturated except flagged OPEN QUESTIONs) | — |

**Search-stop rule applied:** each category pursued until additional query families produced no materially new viable candidates; full query/source log in RESEARCH_LOG.md. No claim of literal exhaustiveness.

---

## 15. Round-2 addendum (2026-08-14, second deep dive — full results in 04-DELTA-round2.md)

A six-track second sweep (~380 additional sources; plan in doc 12) confirmed every Round-1 decision and added these adopt/adapt-grade components: **Terra Draw** (MIT, mission drawing on MapLibre), **@turf/turf** + **react-map-gl/maplibre** + **shadcn-admin** + **uPlot** + **react-grid-layout** (dashboard kit), **DroneRoute** and **map-creator** (MIT orbit/facade/grid math donors), **QGC mission math legally portable under its Apache-2.0 dual-license option** (CameraCalc/Survey/StructureScan), **cameratransform** (MIT framing math), **rtamt** (BSD-3 STL second monitor), **PX4 flight_review + pyulog** (log analysis/CI asserts), **JTS geometry test vectors**, **Parrot tlmb log toolchain** (physical-flight evidence), **pydantic-evals** (MIT, planner eval harness) + **TrustSafeAI 408-prompt drone-safety dataset** (adversarial eval data), **Aerialist** (YAML SITL scenarios), **jonasvautherin/px4-gazebo-headless** (Apache-2.0 Docker image, tags = PX4 releases, built-in sim-camera RTSP proxy = Spike-1 plan B), and the **uv/ruff/mypy/pre-commit/testcontainers/pydantic-settings** toolchain. Key negatives: no permissive web GCS or orbit-planner library exists anywhere; all ideal oblique house datasets are NC-licensed; every drone MCP server gives the LLM raw actuation (one caused a real crash); structured-output benchmarks show valid-JSON ≠ correct-values — the empirical case for our validator. Saturation now claimed for all categories at decision *and* component level, except CV models (re-check at post-MVP kickoff as before).
