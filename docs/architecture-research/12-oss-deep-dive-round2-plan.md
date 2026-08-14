# 12 — Open-Source Deep Dive, Round 2: Plan

**Status:** plan approved-for-execution pending Mike's go — written 2026-08-14. **Objective:** hunt specifically for open source that fits *this* project that Round 1 (doc 04) may have missed — component-level and UX-level reuse, non-obvious ecosystems, and the newest 2025–2026 wave — then update doc 04 to v2 with a "what changed" delta. Round 1 saturated the *decision-level* categories (which simulator, which schema tool); Round 2 hunts *shovel-level* reuse: things that delete weeks of work.

---

## 1. Honest list of suspected blind spots (why Round 2 is justified)

1. **Ground-control-station guts:** we compared mission *formats* but never mined QGroundControl / Mission Planner / Aerostack2 for liftable components or UX patterns (survey/orbit editors, preflight checklists, telemetry widgets).
2. **Web mission-planning UI components:** map-draw plugins (MapLibre/Leaflet draw, turf.js), existing React drone-dashboard or web-GCS projects — Round 1 picked the map engine but never searched for finished mission-drawing UIs.
3. **Behavior trees as executor alternative:** py_trees / BehaviorTree.CPP — the standard robotics alternative to our state machine; never formally evaluated.
4. **Full autonomy frameworks from non-English ecosystems:** XTDrone, Prometheus (Amovlab), GAAS — substantial Chinese-community PX4 autonomy stacks Round 1 never touched.
5. **Flight-log analysis:** PX4 **flight_review** (open-source ULog web analyzer) — potentially adopt-as-is for physical flight logs; missed entirely.
6. **Runtime safety monitoring:** rtamt / STL runtime-verification libraries and "runtime assurance / simplex architecture" implementations — could strengthen the dispatch gate academically and practically.
7. **Photogrammetry-adjacent flight planners:** open orbit/POI/survey *generators* (beyond QGC's C++) — anything that already computes camera-aware orbit rings, roof passes, or facade scans.
8. **Newest LLM-robotics wave (late 2025 → now):** drone MCP servers, VLA models for UAVs (SkyEyeGPT, OpenFLY, AeroVerse...), plan-verification papers with code newer than RoboGuard; plus LLM eval harnesses (inspect-ai, promptfoo) for our planner test suite.
9. **Hugging Face / model hubs:** aerial-imagery detectors and house/roof segmentation models with clean licenses — Round 1 checked architectures, not published fine-tuned weights.
10. **Media pipeline extras:** open photo-culling/selection, HDR merge alternatives, EXIF/geotag tooling beyond exiftool.
11. **Dev/testing tooling for this exact stack:** pytest-asyncio patterns for MAVSDK, Docker compose setups for PX4+gz CI others have already published, GitHub Actions workflows for SITL.
12. **Security bits:** fastapi-users/auth libraries for the eventual LAN-exposed control plane.

## 2. Method — six parallel research tracks

Each track: multiple query *families* (listed below), primary-source verification (LICENSE file, last release/commit, working code not README), verdict per candidate (adopt / adapt / pattern / reference / reject) with 1–2 sentence fit rationale against docs 01/08, and integration-cost estimate. Same evidence labels as Round 1 ([V]/[C]/[I], access-dated). Stop rule per track: two consecutive query families yielding nothing new and viable.

**Track A — GCS, dashboards, mission-UI reuse.** Queries: "web ground control station github", "react drone dashboard open source", "maplibre draw mission planner", "leaflet drone waypoint editor", "QGroundControl survey SurveyComplexItem reuse", "mavlink web ui", "telemetry dashboard drone websocket github". Sources: GitHub topics (ground-control-station, mavlink, uav), npm search, PX4/ArduPilot Discourse show-and-tell threads.

**Track B — autonomy frameworks & executors.** Queries: "XTDrone", "Prometheus Amovlab PX4", "GAAS autonomy", "Aerostack2 mission behavior", "behavior tree drone py_trees", "PX4 offboard mission executor python github", "drone task orchestration ROS2". Evaluate strictly as donors/references vs our core (doc 08 is settled unless something is dramatically better).

**Track C — safety, verification, geofencing, logs.** Queries: "runtime verification robotics rtamt STL monitor", "runtime assurance simplex UAV github", "geofence library python mavlink fence", "PX4 flight_review", "ulog analysis python", "drone safety checklist open source", "InterUSS / UTM open source" (commercial-vision relevance only).

**Track D — photography & CV for aerial real estate.** Queries: "orbit POI waypoint generator github", "roof inspection flight plan open source", "facade scan drone planner", "aerial building detection huggingface", "roof segmentation model license", "photo culling open source", "HDR merge exposure fusion cli", "image quality blur detection library". Include Hugging Face hub sweep with license filter.

**Track E — LLM×drones 2025–2026 wave + eval harnesses.** Queries: "drone MCP server github 2026", "LLM UAV 2026 code", "VLA UAV github", "LLM plan verifier robotics code", "inspect-ai promptfoo LLM eval mission planning", arXiv listings SkyEyeGPT/OpenFLY/AeroVerse/UAV-VLA successors, Papers-with-Code aerial section, UAVs_Meet_LLMs list mined item-by-item (we adopted it as a reading map but never walked every entry).

**Track F — glue, testing, and ops tooling.** Queries: "pytest mavsdk sitl fixture github", "docker compose px4 gazebo harmonic", "github actions px4 sitl workflow", "fastapi websocket telemetry example", "fastapi-users", "pydantic settings secrets pattern", "pre-commit ruff mypy template", "gz transport python camera subscriber example".

## 3. Deliverables when executed

1. **Doc 04 → v2:** new/changed candidates merged per layer, each with license + activity + verdict; unchanged verdicts marked "re-confirmed in Round 2."
2. **Delta report (04-DELTA-round2.md):** what was found that Round 1 missed, what (if anything) changes a decision in doc 08/FINAL, and what was searched with zero result (negative results recorded so we never re-wonder).
3. **research/ additions:** any adopt/adapt-grade repos shallow-cloned + pinned into `research/` with README rows, same protocol as before.
4. **RESEARCH_LOG entry:** full query-family log per track with dates.

## 4. Decision guardrails (so new shiny things don't derail the plan)

A Round-2 find only changes the architecture if it (a) deletes ≥1 week of planned work, (b) is license-clean for the core (MIT/Apache/BSD), (c) is maintained (release or meaningful commit within ~18 months), and (d) doesn't blur the safety boundary. Anything short of that gets logged as reference/post-MVP, and the build proceeds on schedule — Round 2 is insurance, not a restart.

## 5. Cost & timing

Executed as six parallel research agents in one session (~30–45 min wall clock); no purchases, no installs on your machines; output lands in the docs folder like everything else. Recommended timing: now, before M0 coding starts, so any "deletes-a-week" find arrives before the week it would have deleted.
