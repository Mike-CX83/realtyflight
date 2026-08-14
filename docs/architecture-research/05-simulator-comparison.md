# 05 — Simulator Comparison and Decision

**Status:** v1.0 — 2026-08-14. Evidence gathered from primary sources (docs.px4.io, gazebosim.org, ardupilot.org, cyberbotics.com, NVIDIA docs, developer.parrot.com, project repos), all accessed 2026-08-14; full source list in RESEARCH_LOG.md. This is a documentation/source audit — run-verification spikes are scheduled in the roadmap. Labels: **[V]** verified · **[C]** vendor claim · **[I]** inference.

---

## 1. Decision (matches and confirms the CLAUDE.md progression)

1. **Unit/CI workhorse: `FakeDroneBackend`** (our code) — scripted telemetry and faults; covers validator/state-machine/abort logic at unit speed, including cases SITL can't force cleanly (stale telemetry, invented state).
2. **Primary development simulator: PX4 SITL v1.17 + Gazebo Harmonic (`gz_x500_gimbal`)** on Ubuntu (Docker/VM for Mac users) — current-stable, lockstep-deterministic, headless (`HEADLESS=1`), typed fault injection that matches our fault list exactly, gimbal via MAVLink Gimbal v2, free CC0 house assets.
3. **ANAFI-fidelity validator: Parrot Sphinx 2.25** on the Ubuntu+NVIDIA box — runs the **real ANAFI Ai firmware** (firmware-in-the-loop); proves the Olympe adapter, camera2 photo capture, and media download before any physical flight. Not a CI tool (GPU + unofficial headless).
4. **Rejected:** Gazebo Classic (EOL 2025-01-29), AirSim (dead 2022), Colosseum (stale, doc drift, no Apple Silicon), Flightmare/FlightGoggles (last releases 2020/2019), Isaac Sim+Pegasus (RTX-4080-class minimum; one-person version-pinned integration layer; photorealism not on the critical path).
5. **Optional local sandbox: Webots R2025a** (Apache-2.0, native Apple Silicon, built-in `SuburbanHouse`, one-line photo save) — only if Mac-local iteration proves valuable, and only as a sandbox: it has no PX4 path (ArduPilot or custom controllers). Do not split the stack casually.
6. **Watch list:** IAMAI **Project AirSim** (MIT revival of Microsoft's successor by ex-AirSim engineers; v0.2.0 2026-06 — too young), Cosys-AirSim (healthiest AirSim lineage, UE 5.5). Only relevant if photoreal UE rendering later becomes a requirement.

## 2. Comparison matrix (all facts [V] unless noted)

| Simulator | License | OS / GPU | Camera + gimbal | Property worlds | Fault injection | Headless CI | Maintenance (2026-08) | Fit /5 |
|---|---|---|---|---|---|---|---|---|
| **PX4 SITL + gz Harmonic** | BSD-3 + Apache-2.0 | Ubuntu 22/24; modest GPU; no native macOS | `gz_x500_gimbal` (gimbal v2); **photo via gz topics, not MAVLink camera** | Gazebo Fuel houses (House 1 = CC0) on flat worlds | `failure` cmd: gps, battery, mavlink_signal, rc_signal, motor, sensors × ok/off/stuck/garbage/wrong/slow/delayed/intermittent | `HEADLESS=1`, lockstep (cannot disable), `PX4_SIM_SPEED_FACTOR`; PX4's own CI pattern | PX4 v1.17.0 (2026-05-13); gz Harmonic LTS→2029, Jetty LTS→2031 | **5** |
| **Parrot Sphinx 2.25.2** | Proprietary freeware (Parrot apt repo + EULA) | **Ubuntu 20/22/24 + NVIDIA mandatory** (min 2GB; rec. RTX 2070 8GB); Secure Boot off | Full ANAFI Ai camera/gimbal — real firmware; `sphinx-cli camera` record/inspect | UE worlds: `dark-forest` (house+road), CARLA urban maps, forest, office/factory indoor; custom worlds need Parrot UE4 editor build | GPS `out_of_order=true`, wind mean/gust expressions, battery capacity params, motor/ESC temps; link-loss = OPEN QUESTION | `--RenderOffScreen` (user-confirmed, not officially supported); GPU still required | Docs v2.25.2; SDK 8.4 release 2026-05-22 (verified via forum announcements) | **4 as ANAFI validator; 2 as CI** |
| ArduPilot SITL (+ardupilot_gazebo / Webots) | GPLv3 core (LGPL-3 gz plugin) — MAVLink boundary, no linking issue | Linux; macOS incl. M1 for the gz plugin [C] | iris gimbal + zoomable camera; Webots `iris_camera.wbt` | same gz/Fuel assets | `SIM_GPS_DISABLE`, `SIM_RC_FAIL`, wind, noise params | standard headless | Copter 4.6.3 (2025-11); 4.7 beta | 4 (fallback ecosystem) |
| Webots R2025a | Apache-2.0 | **Native macOS Apple Silicon**, Win, Linux | Mavic 2 Pro demo; `wb_camera_save_image` PNG/JPEG; gimbal motors | Built-in `SuburbanHouse`, `ModernSuburbanHouse`, etc. + OSM importer | DIY in controller code (no autopilot faults) | `--no-rendering --batch`; official Docker | R2025a (2025-02); nightlies through 2026-07 | 4 (sandbox only — no PX4 path) |
| Gazebo Classic | Apache-2.0 | — | typhoon_h480 gimbal+video | legacy | works | yes | **EOL 2025-01-29** | 1 — reject |
| Isaac Sim 6.0 + Pegasus 5.1 | Apache-2.0 + BSD-3 | Ubuntu/Win11; **RTX 4080 minimum**; no macOS | RTX cameras; PX4 via Pegasus | NVIDIA USD assets | not mission-fault oriented | container headless-only | Isaac 6.0 (2026-06, now open source); Pegasus one-maintainer, pinned to Isaac 5.1 | 2 — reject for scope |
| AirSim / Colosseum / Cosys-AirSim | MIT | UE-weight; no Apple Silicon (Colosseum) | AirSim APIs | UE packs ($) | AirSim-style | UE-heavy | dead 2022 / stale 2023 (docs drift) / v3.3 2025-04 | 1 / 1 / 2 — reject |
| Flightmare / FlightGoggles | MIT/unclear | Linux | RL-oriented RGB | Unity | no | partial | last releases 2020 / 2019 | 1 — reject |
| Project AirSim (IAMAI) | MIT | Win11/Ubuntu22; UE 5.2/5.7 | AirSim lineage | UE packs | unknown | unknown | v0.2.0 (2026-06-01) — too young | 2 — watch |

## 3. The architectural payoff of this pairing

- **PX4 path** exercises the *hardware-independent* claim: `MissionPlan → PX4Backend (MAVSDK v3.17) → SITL`, with `Action.do_orbit` as fast-path and waypoint-ring orbit as the portable form (doc 04 §5).
- **Sphinx path** exercises the *owned-drone* claim with near-zero adapter drift: **Olympe speaks to the simulated ANAFI Ai exactly as it speaks to the physical one** (same API; the switch is an IP address — sim `10.202.0.1`, WiFi `192.168.42.1`, SkyController `192.168.53.1` [V: Olympe examples]). Passing Sphinx ⇒ the physical demo is a controlled repeat, which is precisely the simulator-first promise.
- Same `MissionPlan` through both backends = the capstone's marquee slide. [I]

## 4. Known costs and open questions (feed doc 10 + week-1 spikes)

1. **gz photo capture:** the simulated gz camera is *not* exposed over the MAVLink camera protocol ("cannot yet be used… for image capture" [V: PX4 vehicles doc]) ⇒ `PX4Backend.capture_photo()` = command gimbal via MAVLink + grab frame from the gz camera topic (official Python gz-transport bindings [V]) + log as evidence. Spike scheduled (V4).
2. **Sphinx camera2/media in-sim:** expected to work because Sphinx runs the real firmware (web server included) [I]; **OPEN QUESTION** — week-1 spike on the Linux box: take a camera2 photo in Sphinx and download via `olympe.Media`.
3. **Sphinx link-loss injection:** not documented on pages read; leads: WiFi `stolen_interface`, network-emulation forum threads. OPEN QUESTION.
4. **macOS reality:** PX4+gz not native on Apple Silicon (official mac env covers Classic under Rosetta only [V]) ⇒ standardize on one Ubuntu box + Docker/CI; Macs use Ubuntu arm64 VMs (UTM/OrbStack) or remote the box.
5. **Official PX4 gz-Harmonic Docker image:** none confirmed under px4io [V: PX4-containers]; community images exist — pin our own Dockerfile. OPEN QUESTION on official tag.
6. **World:** PX4 `lawn`/`default` world + Fuel "House 1" (CC0) + fence/trees + our geofence config = the simulated property; per-model Fuel licenses checked individually. Sphinx stock `dark-forest` has a house; custom UE world only if time allows (needs the Parrot UE4 editor pipeline, ≥40 GB).

## 5. CI pattern (verified against serious projects)

PX4's own CI runs headless lockstep SITL integration tests in Docker with `--speed-factor 10 --abort-early`, and still fights flakiness — so: keep mission/policy logic in plain unit tests against the FakeBackend (fast, deterministic), and gate PRs with a *small* scripted SITL suite (takeoff→orbit→capture→RTH + one fault scenario), nightly for the fuller matrix. Aerostack2 likewise keeps Gazebo out of CI and ships a lightweight non-Gazebo sim platform for tests — same philosophy as our FakeBackend. [V: PX4 sitl_tests.yml; Aerostack2 CI workflow]

## 6. Path from simulation to physical flight (gates in doc 10)

FakeBackend (weeks 1–) → PX4 SITL/gz demo complete (mid-project) → Sphinx + Olympe adapter passes the same mission (Gate G4) → bounded physical ANAFI Ai test: manual-override armed, conservative envelope, Part 107 holder, private property (Gate G5). No autonomous command reaches the physical drone before its Sphinx twin has executed the identical mission.
