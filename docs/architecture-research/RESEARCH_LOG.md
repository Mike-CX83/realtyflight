# RESEARCH_LOG

Reproducible log of research activities: what was done, how, when, with what evidence standard. Newest entries last. Evidence labels used across all docs: **[V]** verified against a primary source read on the stated date · **[V-code]** verified in downloaded source/protocol files · **[C]** vendor/repo claim not independently confirmed · **[I]** inference · **[OQ]** open question requiring a test.

---

## 2026-08-14 — Session 1 (Phases 1–5 initial pass)

### 1. Inputs read
- `AI_Autonomous_Real_Estate_Drone_Master_Architecture_Prompt.md` (uploaded copy, 26 KB) — master prompt.
- `CLAUDE.md` (18 KB, read via device bridge) — project context, five-repo hypotheses, progression, guardrails.

### 2. Workspace inventory (read-only, via device bridge to /Users/mike/Desktop/capstone_drone)
Commands (device VM shell): directory listing; `git remote/branch/log/rev-list` per subdir (with `safe.directory=*` retry); `.git` dirent inspection; `du -sh`; README/LICENSE read attempts.
Findings: root repo `git init` with zero commits/no remote; five repo copies present (sizes 4.4–26 MB); `mavsdk_drone_show/.git/shallow` ⇒ depth-1 clone; **all repo file contents are iCloud placeholders — reads fail with EDEADLK; `device_stage_files` confirms "cloud placeholder (not downloaded)"**. User notified with remediation steps (Finder → Download Now / disable Optimize Mac Storage). Materialization check retried later in session: still pending. → **Pending-1** in docs 02/03.

### 3. External research method
Four parallel evidence-gathering agents (web + registry + raw-file reads) + one upstream-repo audit agent, each instructed to: use primary sources; read actual LICENSE files and release pages; label every claim [V]/[C]/[I]; include URL + access date 2026-08-14; mark unresolved items OPEN QUESTION; never fabricate URLs/versions. Their complete per-claim source URL lists are embedded in their scoped outputs, which were synthesized into docs 03–06; headline sources repeated below.

Agent scopes & approximate coverage:
- **A1 Parrot/ANAFI ecosystem** (~103 fetches): parrot.com product/newsroom/support + earnings, developer.parrot.com (Olympe/Sphinx/AirSDK docs), **parrot-olympe 8.4.0 wheel downloaded from PyPI and inspected** (arsdk XMLs: move, ardrone3, followme, onboard_tracker, auto_look_at, animation, gimbal, rth, flight_plan; protobufs: camera2, geofence; examples; controller.py; pdraw.py), GitHub Parrot-Developers, forum threads incl. staff answers (copiloting 13104, headless 14643, docker 16369, indoor 19432, FF7-Android 18352), github.com/topics/anafi community scan (anafi_ros, anafi_autonomy, qgc-mavlink-converter, olympe-dockerfile…).
- **A2 Simulators** (~108 fetches): PX4 releases/user-guide raw (sim index, gz vehicles, failure_injection, gimbal_control, dev_env_mac, docker, sitl_tests.yml CI), gazebosim.org (releases/EOL, install, transport Python API), classic.gazebosim.org EOL, ArduPilot (releases, COPYING, simulation docs, ardupilot_gazebo, Webots integration), Webots (releases, system reqs, camera API, mavic2pro controller source, SuburbanHouse proto, OSM importer, docker), Isaac Sim 6.0 repo + requirements, PegasusSimulator, AirSim/Colosseum/Cosys/ProjectAirSim(IAMAI), Flightmare/FlightGoggles, aerial_gym, RotorPy, PyFlyt, gym-pybullet-drones, Aerostack2 (+CI workflow), MAVSDK releases, Gazebo Fuel house models (House 1 CC0), Fab suburb pack listing, blosm.
- **A3 LLM/mission/orchestration OSS** (~73 fetches): PyPI/npm registry JSON for pydantic, pydantic-ai, instructor, outlines, langgraph, litellm, baml-py, llama-cpp-python, ollama, python-statemachine, transitions, xstate, temporalio, eventsourcing, jsonschema, shapely, guardrails-ai, rerun-sdk, structlog, opentelemetry, fastapi, uvicorn, websockets, maplibre-gl, leaflet, faster-whisper, ctranslate2, vosk, moonshine-voice; raw LICENSE files for each adoption candidate; MAVLink mission protocol; QGC .plan format; MAVSDK-Proto mission/action; PX4 orbit + mission-command docs; Parrot FlightPlan docs; UgCS/FlytBase docs; Foxglove archive/pricing + Lichtblick LICENSE; LLM-drone repos: PromptCraft, TypeFly (+arXiv/TMC), AUSPEX (+Frontiers 2025 paper), RoboGuard/SPINE (+arXiv), UAV-VLA, EchoPilot (+PX4 forum), DeepDrone, ChatDrones, embodied-drone-agents, MAVLink-AI-Agent, Leviosa, UAVs_Meet_LLMs, MDS.
- **A4 CV/photography/domain** (~92 fetches): industry guides (Drone Launch Academy, JOUAV, HDRsoft real-estate HDR, Vantage pricing, Fotober MLS specs), parrot.com camera tech docs (bracketing 3/5/7), FAA (commercial_operators, remote_id, over-people, eCFR 107.19/107.51, Federal Register Part 108 NPRM reopening 2026-01-28, airdata OIRA tracking [C]), detection/tracking/seg/depth repos + LICENSE files (ultralytics AGPL, YOLOX, RT-DETR, RF-DETR split licensing, D-FINE, mmdetection, ByteTrack, BoT-SORT, Norfair, supervision, SAM2/SAM3 license, DepthAnythingV2 variant licenses, Metric3D, ml-depth-pro license), IQA (opencv_contrib quality README, piq, pyiqa PolyForm-NC), imaging (rawpy, libraw.org, exiftool, exiv2, OpenCV HDR module, enblend), photogrammetry (ODM/WebODM AGPL, COLMAP, Meshroom, nerfstudio, gsplat), SLAM (ORB-SLAM3, VINS-Fusion, OpenVINS, RTAB-Map, Kimera), cinematography (CineMPC arXiv+repo no-license, CMU airlab page, AirCap GPL, agentic-cinematography 2025 arXiv), path math (MAVSDK do_orbit API, gimbal v2 protocol, QGC survey, Fields2Cover).
- **A5 Workspace upstream audit** (~83 fetches): identified all five upstreams (high confidence): alireza787b/mavsdk_drone_show (LICENSE + LICENSE-NONCOMMERCIAL.md + CHANGELOG + agent_policy.yaml + agent_tools.yaml + agent_runtime files + 691-line test file + simurgh-operator guide + 2026-07-27 feasibility checkpoint read); alireza787b/dronesphere (full tree via API; **validator.py and both test files verified 0-byte**; llm_handler keyword-fallback verified; no LICENSE); pratikPhadte/LLM-controlled-drone (API metadata: created+pushed 2026-02-25 within ~32 min; brain_node/llm_client/command_translator read; prompt-as-flight-controller verified; no LICENSE); ai-in-pm/FPV-Drone-AI-Agent (README "Closed License", RAIL-AMS doc, GPL Betaflight headers vendored, MissionTypes.hpp + RuleEngine.cpp read; ~4 h repo lifespan); Hacker0x01/claude-power-user = fork of obra/superpowers (MIT).

### 4. Lead-session spot verifications (defense against agent error)
- Sphinx system requirements page fetched directly: Ubuntu 20/22/24 + NVIDIA (min 2 GB, rec. RTX 2070 8 GB), Secure Boot off. ✔ matches A1.
- MDS LICENSE fetched directly: PolyForm NC / SB(+<10 drones, <100 employees, <$1M) / negotiated commercial; attribution mandatory. ✔ matches A5.
- Olympe release dating discrepancy resolved: GitHub shows "20 May" (year omitted ⇒ within 12 months ⇒ **2026-05-20**); forum announcement "Parrot Drones SDK + Sphinx 8.4 release" dated 2026-05-22 confirms; an initial summarizer guess of "2025" rejected. PX4 v1.17.0 = 2026-05-13 (stable) confirmed. (PyPI JSON blocked by robots for the lead session; A1 had registry access.)

### 5. Key decisions recorded today (all preliminary until gates)
- Sim pairing: FakeBackend → PX4 SITL+gz Harmonic (primary) → Sphinx (ANAFI validation). Rejections logged in 05.
- ANAFI Ai: **conditional go** (06 §8), indoor autonomy deferred on staff-verified platform limits.
- No agent framework; PydanticAI+Pydantic structured output; python-statemachine; custom policy engine + Shapely; SQLite events + structlog (+Rerun replay); FastAPI/React/MapLibre; Web Speech + faster-whisper.
- Foundation strategy → Gate G1 (greenfield-lean preliminary vs MDS-chassis), Linux box → G2.

### 6. Saturation assessment
Per-category status in 04 §14 (saturated for decision purposes except: CV re-check at post-MVP kickoff; cinematography leads open). Search-stop rule: additional query families stopped yielding materially new viable candidates. No literal-exhaustiveness claim.

### 7. Open questions carried forward
OQ-1 Sphinx camera2 photo + Media download in-sim (spike, G2 box). OQ-2 OA behavior during extended_move_to (Sphinx test). OQ-3 classic moveTo on ANAFI Ai (Sphinx test). OQ-4 Sphinx link-loss injection method. OQ-5 official PX4 gz-Harmonic Docker tag. OQ-6 camera2 zoom/exposure-lock exact symbols (doc page 403'd; wheel has proto — re-read). OQ-7 roboflow `trackers` package license. OQ-8 xView dataset terms. OQ-9 local repo commits vs upstream (Pending-1, blocked on iCloud download). OQ-10 Part 107 holder availability on team.

### 8. Next session plan
1. If iCloud materialized: complete Pending-1 (pin commits, diff MDS vs upstream) and finalize doc 02/03 dispositions.
2. Phase 6: full architecture (08) — schema v1, state machine, DroneBackend contract, safety catalog, diagrams.
3. Phase 7: roadmap (09) + risk re-score (10).
4. FINAL_RECOMMENDATION: answer the 25 questions; present G1/G2 decision briefs to Mike.

---

## 2026-08-14 — Session 2 (Pending-1 closure; Phases 6–7; final recommendation)

### 1. Local repository pinning (Mike confirmed access; iCloud contents downloaded)
Commands (device VM shell, `safe.directory=*`): `git config --get remote.origin.url` + `git log -1` / `git rev-parse HEAD` per repo; targeted `ls`/`wc -c` verifications.
Results (all recorded in doc 02 §2): claude-power-user @ `495f82d` (Hacker0x01 fork, merge from obra:main 2025-11-12); dronesphere @ `22fc485` (2025-09-30 = upstream final); FPV-Drone-AI-Agent @ `10e69d7` (2026-03-08 = upstream final); LLM-controlled-drone @ `fc3f400` (2026-02-25 = upstream final); mavsdk_drone_show @ `30899be` (shallow depth-1; `git log` Bus-errors through the mount, `rev-parse` + `.git/shallow` agree; file mtimes 2026-08-11).
Local spot-verification against the upstream audit: dronesphere `agent/validator.py`, `tests/test_basic.py`, `tests/test_integration.py` = **0 bytes on disk**; no LICENSE files locally in dronesphere / LLM-controlled-drone; FPV `MissionTypes.hpp` + `RuleEngine.cpp` present; **local MDS contains the Simurgh layer** (agent_policy.yaml 1,464 B; agent_tools.yaml 114,136 B; `gcs-server/agent_runtime/` incl. action_intent/action_planner/action_preconditions/approvals/audit; simurgh-operator guide; foundation test file). Residual: a few individual files still lazy placeholders (MDS CHANGELOG.md, dronesphere llm_handler.py, two README/LICENSE files) — noted in doc 02 §3, immaterial (audited upstream at same commits).
→ Pending-1 + Pending-2 CLOSED; R10 CLOSED; docs 02/03 updated to v1.0.

### 2. Phase 6 — target architecture (doc 08 v1.0)
Authored from settled inputs only (no new external claims): three-zone trust model; component/deployment topology; MissionPlan schema v1 (field-level, discriminated unions, extra=forbid, unit-suffixed); shot-library compilation; 17-rule policy catalog (static + dispatch-gate); evidence-gated state machine (MDS-adopted landing thresholds: alt ≤1.0 m, |vspeed| ≤0.75 m/s); DroneBackend protocol v1 + error taxonomy + capabilities; orbit-as-engine-behavior (waypoint ring; PX4 do_orbit fast-path); event taxonomy + replay; security profiles (sim/real, ENV-01); five-level test seam plan.

### 3. Phase 7 — roadmap (doc 09 v1.0)
M0–M8 (Sep 2026–May 2027) + June buffer; roles R1–R3; per-milestone acceptance tests; MVP spine gate-independent; stretch spine G2→M5(Sphinx/G4)→G5→M6(physical, earliest Mar 2027); budget $0 MVP / ≤$1,025 fully-loaded stretch; weekly cadence + monthly risk re-score.

### 4. FINAL_RECOMMENDATION v1.0 issued
All 25 master-prompt questions answered decisively; stack table with primary/fallback/rejected + confidence; custom-software list (4–7 kLOC Python + 2–3 kLOC TS); G1 recommendation = greenfield-lean core with MDS as reference/donor (alternative preserved); G2 recommendation = borrow-then-buy-used Ubuntu/RTX box by M2 exit; G5 RPIC plan due January. Research phase closed; next log entries belong to implementation (M0).

### 5. Gate G2 resolved by disclosure (same day)
Mike disclosed owned hardware: custom Clevo/Sager NH58AF laptop — AMD Ryzen 7 3800XT (8c), NVIDIA GeForce RTX 2070 Mobile, 32 GB DDR4 G.Skill SODIMM, 2 TB SanDisk SSD, dual-boot Windows 11 Home + Linux (CPU/RAM/storage upgraded; OEM keyboard replaced). Cross-checked vs Sphinx system requirements (verified 2026-08-14): GPU = recommended tier (RTX 2070 8 GB), CPU = 8-core minimum met, RAM/disk exceed recommended. **G2 CLOSED at $0**; R2 downgraded. Residual M0 checks recorded in docs 00/06/09/10/FINAL: Linux partition must be Ubuntu 20.04/22.04/24.04 x86_64, UEFI Secure Boot disabled, current NVIDIA proprietary drivers. Consequence: Sphinx spikes (OQ-1/2/3) can move from M5 up to M0 week 1.

### 6. Round-2 OSS deep dive executed (same day; plan = doc 12, results = 04-DELTA-round2.md)
Six parallel research tracks (A GCS/dashboard-UI · B autonomy frameworks incl. XTDrone/Prometheus/GAAS/Aerostack2/behavior-trees · C safety/runtime-verification/geofence/logs · D camera-aware planning/aerial CV/photo pipeline · E 2025-26 LLM-drone wave + eval harnesses + UAVs_Meet_LLMs item-walk · F Docker/CI/pytest/frontend/toolchain), ~380 sources, licenses read from LICENSE files, several claims verified by execution (rtamt install workaround + past-time STL monitoring; QGC dual-license COPYING.md; pydantic-evals existence v2.30.0 same-day release). Outcome: zero architecture changes; 14 adopt/adapt components (est. 3–5 weeks of work deleted); Spike-1 gotcha (gz Python bindings apt-only, no PyPI wheels) + plan B (headless image's RTSP camera proxy); executor "concurrent failsafe watcher" idiom adopted as pattern; BT-vs-FSM decisively settled for FSM (SteelEagle 2026 corroboration); physical-flight evidence pipeline identified (Parrot fdr-lite → tlmb tools; blackbox log.bin encrypted — never promise it). Track agent outputs preserved in session records; top finds + negatives merged into 04 §15 and 04-DELTA-round2.md. New research/ pins: droneroute @2b27ac2d, map-creator @bf7485af, Aerialist @aa5118a9, qgc-mission-math (Apache election + attribution).

### 6b. Decisions closed by Mike (same day)
- **G1 = greenfield-lean** (Mike's explicit call after full trade-off discussion; MDS = read-only reference, no code lifted; TODO C4 demoted to optional learning).
- **G2 = closed at $0** (owned Clevo/Sager NH58AF, RTX 2070 — recorded earlier this session).
- **G5 RPIC identified: Cliff Flock, Part 107 certificated** (availability confirmation due at M4 review; R13 downgraded).
All three recorded in docs 10 / FINAL / TODO. Remaining open human item: B2 team roster (names + weekly hours).

### 7. Reference-repo pull-in (earlier same day, on Mike's request)
Created isolated `research/` per master prompt §6. Shallow-cloned in the cloud (device VM has no network), transferred as tar.gz, unpacked on device, commits verified on disk: RoboGuard @ `e5606aa` (MIT), SPINE @ `e776a8a`, AUSPEX @ `365f10e` (v2.0.26, MIT). Transfer archives moved to `research/_to_delete/` (device shell cannot rm — Mike trashes it). Library-type "keepers" (pydantic/pydantic-ai/python-statemachine/shapely/fastapi/mavsdk/faster-whisper/rerun/maplibre/olympe) deliberately NOT vendored — recorded as pinned installs in `research/README.md` §2; PX4/Gazebo/Sphinx are toolchain installs for the G2 box, not folder contents.
