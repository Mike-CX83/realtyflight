# 04-DELTA — Round-2 Deep Dive Results (what Round 1 missed)

**Executed 2026-08-14 per plan doc 12: six parallel tracks (A GCS/UI · B autonomy frameworks · C safety/verification/logs · D photography/CV · E LLM-drone 2025-26 wave · F glue/testing/ops), ~380 sources checked, licenses read from actual LICENSE files.** Full per-track evidence and negative-result logs archived via RESEARCH_LOG session 2 §7. Verdict up front: **the architecture (doc 08) stands unchanged — nothing found supersedes any settled decision — but Round 2 surfaced 14 adopt/adapt-grade components that delete real weeks of work, one new plan-B for Spike-1, one physical-flight evidence pipeline, and several load-bearing negative results.**

---

## 1. New ADOPT/ADAPT-grade finds (pass the guardrail: permissive + maintained + deletes work)

### Dashboard / UI (Track A) — directly answers the "AI builds ugly websites" worry
| Find | License / freshness | What it deletes |
|---|---|---|
| **Terra Draw** + maplibre adapter (JamesLMilner/terra-draw) | MIT; v1.32.3 published 2026-08-08 | 1–2 weeks of property-boundary/waypoint draw-edit tooling — polygon/circle/point draw, select, drag, snap, on MapLibre; officially listed MapLibre plugin |
| **@turf/turf** | MIT; v7.4.0 2026-08-03 | All UI-side geometry math (area, contains, self-intersection `kinks`, buffer) — mirrors the server validator for instant map feedback |
| **react-map-gl `/maplibre`** (vis.gl) | MIT; v8.1.2 2026-07-29 | React↔MapLibre lifecycle plumbing; no Mapbox token needed |
| **shadcn/ui + shadcn-admin shell** (satnaing) | MIT; CLI 2026-08-13 / shell 2025-11 | ~1 week of dark "mission-control" layout/nav/theme chrome |
| **uPlot** | MIT; 1.6.32 (2025-03) | Smooth 10–50 Hz live telemetry charts + replay scrubbing (Recharts keeps the low-rate sparklines) |
| **react-grid-layout** | MIT; 2.2.4 2026-07-29 | Draggable/resizable widget dashboard (the Cockpit-style UX, license-clean) |
| **react-gauge-component**, **vis-timeline** (MIT / Apache-or-MIT, both 2026-active) | — | Battery/speed gauges; mission event timeline synced to replay |

### Mission math donors (Tracks B+D) — the shot-library geometry is no longer invented from scratch
| Find | License / freshness | What it deletes |
|---|---|---|
| **DroneRoute** (fcsonline/droneroute) | MIT; v0.7.2 2026-07-13 | Field-tested **orbit** (per-waypoint heading-to-center + `gimbal pitch = −atan2(height, radius)`), **facade-scan raster**, lawnmower grid generators with sane defaults — port from TS to Python, 1–2 days, saves 3–5 days + debug |
| **map-creator** (hdrpano) | MIT; v1.0.4 2026-05-09 | Python orbit/helix/POI-circle mission math + DJI-KMZ/Litchi exporters; the only MIT+maintained *Python* orbit source found |
| **QGroundControl mission math** — dual-license discovery: QGC is **Apache-2.0 OR GPL-3.0 at your choice** (COPYING.md verified) | v5.0.8 2025-10 | `CameraCalc.cc` (camera footprint/overlap→spacing), `SurveyComplexItem`, `StructureScanComplexItem` (layered orbit around a structure — the roof/building-scan case) become legally portable under the Apache election with attribution — weeks of tested geometry |
| **cameratransform** (rgerum) | MIT; PyPI 2025-07 | Peer-reviewed camera↔world projection: "will the house fill the frame from this waypoint" framing/footprint checks |
| **MAVSDK `do_orbit`** re-confirmed + **SAHI** (obss, MIT, 2026-05) for post-MVP small-object slicing | — | — |

### Safety, verification, and evidence (Track C) — hardens the defense story
| Find | License / freshness | Value |
|---|---|---|
| **rtamt** (STL runtime monitor) | BSD-3; commit 2025-11 | Academically-citable *second monitor* beside our policy engine: `historically(alt ≤ ceiling)`, `historically(telemetry_age ≤ 2s)` over the live stream + offline over sim logs in CI. **Hands-on verified by the research agent**: installs only with `setuptools<58` + `antlr4-python3-runtime==4.7` pin (isolate in its own venv), and online mode needs past-time specs (`historically`, not bare `always`) — both workarounds tested working. ~1 day, optional, never gates actuation |
| **PX4 flight_review + pyulog** | BSD-3; 2026-06 / 2026-08 | Zero-code web analysis of every SITL flight log + programmatic ULog assertions in CI ("max alt < ceiling", "no failsafe flags") |
| **MAVSDK geofence upload** | BSD-3 | Push our same boundary polygon into PX4 itself in SITL — a third, autopilot-enforced fence layer to test divergence against |
| **JTS test suite vectors** (locationtech/jts, EDL/BSD-style) | active | Battle-tested point-in-polygon edge cases (boundary/vertex/hole) → imported as pytest vectors for our Shapely fence (~0.5 day, deletes ~a week of adversarial test authoring) |
| **Parrot tlmb toolchain** (Parrot-Developers/telemetry + logger, both BSD-3) | official, stale but Sphinx docs still reference | **The physical-flight evidence pipeline:** ANAFI Ai produces downloadable `fdr-lite` records via its web API → `logextract.py` + `tlmb2csv.py` yield an independent 5 Hz position record to audit geofence/ceiling compliance after the G5 flight; the same format captures Sphinx *ground-truth* logs. Vendor the 3 scripts (~1 day). **Key fact: full ANAFI blackbox `log.bin` is encrypted — never promise blackbox analysis** |

### Planner eval + testing (Tracks E+F)
| Find | License / freshness | Value |
|---|---|---|
| **pydantic-evals** | MIT; v2.30.0 released 2026-08-14 (same day) | The planner eval harness question is settled: it's part of the PydanticAI family — YAML/JSON case datasets + custom deterministic evaluators (our own validator as the scorer), runs in pytest/CI. Beats inspect-ai (heavyweight) and promptfoo (Node dep; **acquired by OpenAI 2026-03**) |
| **TrustSafeAI physical-safety benchmark** | MIT; HF dataset | 408 drone-specific attack/violation prompts — a ready-made adversarial eval set where the expected outcome is *rejection*; plugs straight into our "evil requests" file |
| **Aerialist** (skhatiri) | MIT; v1.0 2025-09 | YAML-specified PX4-SITL test cases (env, wind, commands, expectations) + Docker — adapts into our scenario runner, saves ~a week of harness plumbing |
| **jonasvautherin/px4-gazebo-headless** Docker image | Apache-2.0; tags map 1:1 to PX4 releases incl. **1.17.0**; rebuilt ~2 weeks ago | **The SITL bring-up shortcut:** one `docker run` gives PX4 SITL + gz Harmonic headless with MAVLink on UDP 14540 — works on the Macs via Docker Desktop too. Bonus: it ships an **RTSP proxy for the sim camera** (`rtsp://…:8554/live`) |
| **testcontainers + pytest-asyncio + pyulog** (Apache/Apache/BSD, all 2026-active) | — | The conftest recipe: fixture owns the SITL container lifecycle; ULog assertions post-mission |
| **Toolchain pins** (Track F): uv (MIT/Apache, the 2026 default), ruff (lint+format, steal MAVSDK's `--select=ASYNC,PERF`), mypy 2.x, pre-commit, pydantic-settings for the sim/real profile split, FastAPI docs ConnectionManager WS pattern | — | Settles TODO item D2's toolchain with zero debate |

## 2. Two Spike-1 changes (gz camera frame grab)

1. **Gotcha found:** the gz Harmonic Python bindings have **no PyPI wheels** — apt-only (`python3-gz-transport13`), so the camera-subscriber code runs on the Ubuntu laptop or in-container with `--system-site-packages`. Budgeted into the spike.
2. **Plan B found:** the adopted headless image's built-in RTSP proxy means `cv2.VideoCapture("rtsp://…:8554/live")` grabs frames with zero gz bindings — a 10-line fallback that also works from the Macs.

## 3. One executor improvement (pattern only, ~1 day, scheduled into M1)

From the behavior-tree evaluation (Track B — decisive verdict: **keep python-statemachine**; BTs suit reactive tick-based robotics, not linear pre-approved missions; corroborated by CMU's 2026 SteelEagle converging on an async FSM): steal BT-land's *eternal guard* idiom — run failsafe telemetry watchers as **concurrent asyncio tasks that can preempt the current state at any time**, instead of checking guards only at state boundaries. Added to doc 08's executor notes.

## 4. Load-bearing negative results (searched, empty — never re-wonder)

1. **No MIT/Apache web GCS with liftable React components exists** — every serious one is GPL/AGPL/PolyForm (ADOS, Cockpit, Skybrush, ArduDeck, MDS). Our custom dashboard is justified; mine them for UX only.
2. **No permissive, maintained Python orbit/roof-pass planner library** — clean options are apps to port from (DroneRoute, map-creator), not importable libs; the best full planner (HOTOSM drone-flightplan) is AGPL.
3. **No oblique-drone house detector with clean weights on Hugging Face**, and **every ideal oblique residential dataset is non-commercial-licensed** (VDD, Semantic Drone, UAVid, DOTA) — clean data = FloodNet (CDLA-Permissive) + self-captured/sim frames. Zero-shot GroundingDINO/OWLv2 (Apache) is the no-training baseline.
4. **No pytest+MAVSDK fixture package, no Sphinx 2.x CI recipe, no official PX4 gz-Harmonic Docker image** — community image + own conftest is the path (parts adopted above).
5. **No adoptable runtime-assurance/Simplex library** (the AFRL one has a "government owned" non-license) — our custom gate stands; frame it as a Simplex instance citing the taxonomy.
6. **Every drone MCP server hands raw actuation to the LLM** — one (droneserver) deprecated its `pause_mission` tool *after it caused a real crash in testing*: a citable exhibit for our validator-in-the-middle design.
7. **Structured-output benchmarks (2026)**: schema *validity* is ~solved (84–99.9%) but exact-value *correctness* tops out ~83% — syntactically valid ≠ safe, which is the empirical justification for the deterministic validator + approval. Keep the schema simple to stay inside every engine's supported subset.
8. pyiqa is PolyForm-NC (re-confirmed), Foxglove closed (re-confirmed), encode/broadcaster archived, no clean horizon-tilt/GSD/real-estate-enhancement libraries — all hand-roll/deterministic plans confirmed.

## 5. What was pulled into `research/` (pinned, isolated, read-only)

`droneroute/` (MIT, @2b27ac2d — docs/ media stripped), `map-creator/` (MIT, @bf7485af), `Aerialist/` (MIT, @aa5118a9 — samples/ stripped), `qgc-mission-math/` (six MissionManager files + Apache license copy + attribution note). Library adopts (terra-draw, turf, uPlot, pydantic-evals, rtamt, pyulog, testcontainers…) enter as pinned installs at M0, not vendored source.

## 6. Bottom line

Round 2 was worth running: it found no reason to change course (the strongest possible validation of Round 1's decisions) while cutting an estimated **3–5 weeks of cumulative work** — mission-drawing UI, orbit/facade/footprint math, SITL bring-up, test harness, planner eval, fence test vectors — and adding a physical-flight evidence chain plus a second formal safety monitor that will both play well in the capstone defense. The build plan (TODO.md) absorbs all of it without moving a single milestone.
