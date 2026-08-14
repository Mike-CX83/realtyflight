# 06 — ANAFI Ai Capability Assessment

**Status:** v1.0 — 2026-08-14. **Preliminary verdict: CONDITIONAL GO** (conditions in §8).
**Evidence:** primary sources — developer.parrot.com (Olympe/Sphinx/AirSDK docs), the actual `parrot-olympe` 8.4.0 wheel downloaded from PyPI and inspected (arsdk XML feature files + protobufs + examples), parrot.com product/support/newsroom pages, Parrot H1-2026 earnings release, forum.developer.parrot.com threads with Parrot-staff answers. Full URL list in RESEARCH_LOG.md; all accessed 2026-08-14. Labels: **[V]** verified (page or code read) · **[V-code]** verified in the 8.4.0 wheel's protocol definitions · **[C]** vendor claim · **[I]** inference · **[OQ]** open question requiring a test.

---

## 1. Ecosystem health — the strategic picture

- Parrot is now a profitable defense/enterprise micro-UAV company: H1-2026 revenue €57.3M (+71%), 74% from professional micro-UAVs led by ANAFI UKR. [V: earnings release]
- ANAFI Ai remains listed as a current product; **its consumer-facing firmware/app are frozen**: drone FW 7.7.1 with the FreeFlight 7 iOS app last updated 2023-08 (~3 years). FreeFlight 8 / FW 8.x is ANAFI UKR-only. [V]
- **The SDK line is alive because the defense products share it:** Olympe **8.4.0 released 2026-05-20** (major rework; confirmed against the GitHub release + the forum's "Parrot Drones SDK + Sphinx 8.4 release," 2026-05-22), GroundSDK 8.4.2 (2026-07-17), Sphinx 2.25.2 — all explicitly retain ANAFI Ai. Parrot staff still answer forum threads (activity through 2026-08-11). [V]
- **Risk framing:** a maintenance-mode consumer platform on an actively maintained SDK. Mitigation = backend-neutral core with the PX4 path as exit ramp (already our architecture). [I]

## 2. Requirement-by-requirement assessment (master prompt §2 items)

| # | Requirement | Finding | Evidence |
|---|---|---|---|
| 1 | Professional-quality stills | 48 MP 1/2" CMOS, 4K60 video, 6× zoom claims; adequate for MLS deliverables (≥2048 px). Optical quality vs DJI peers unbenchmarked by us | [C: product/tech docs] [I] |
| 2 | RAW, exposure control, bracketing | **Yes, programmatic:** camera2 API — `PHOTO_MODE_SINGLE/BRACKETING/BURST/TIME_LAPSE/GPS_LAPSE`; brackets 3/5/7 frames (±1/2/3 EV); `DNG_JPEG` format; exposure modes incl. full MANUAL (ISO 25–51200, shutter 1/10000–1 s, EV ±3 in 1/3 steps); 18 WB modes | [V-code: camera2.proto] |
| 3 | Stable video + controllable gimbal | 3-axis stabilization [C]; gimbal API: `set_target` position/velocity per-axis, relative/absolute frames, max-speed, bounds events | [V: gimbal docs + V-code] |
| 4 | Outdoor autonomous missions | **Yes:** `move.extended_move_to/by` with per-move speed caps (ANAFI Ai-specific, `support=091a`); MAVLink FlightPlan (`common.Mavlink.Start`, FlightPlan V2, `MissionItemExecuted` events); preconditions incl. GPS fix | [V-code: move.xml, flight_plan.xml; V: docs] |
| 5 | Indoor / GPS-denied navigation | **No (for autonomy).** Parrot staff: "guided piloting… is not available in indoors conditions"; "ANAFI series drones don't know their positions in GPS-denied environments… not possible to add any velocity or relative position control." Vision-based *manual-rate* hover only (<5 m AGL claimed) | [V: forum 19432 staff answer] [C: white paper] |
| 6 | Obstacle sensing / avoidance | Yes: `obstacle_avoidance.set_mode(disabled|standard)` + status/alerts (incl. drone-frozen alert); OA active during autonomous flight up to 8 m/s claimed; interplay with extended_move_to not documented | [V: OA docs] [C: white paper] [OQ: behavior during our moves — test in Sphinx] |
| 7 | VIO/SLAM/mapping/external localization | Not exposed. No SLAM/VIO features in the 8.4.0 protocol set; no external position input accepted | [V-code: feature inventory] |
| 8 | Subject/property tracking | Classic `followme` **not** flagged for ANAFI Ai; instead `onboard_tracker` (add target from rect/proposal) + `auto_look_at` (both `support=091a`). Piloted-POI v2 flagged for older models only | [V-code: followme.xml, onboard_tracker.xml, auto_look_at.xml] [OQ: verify POI-style behavior in Sphinx] |
| 9 | Live video + telemetry | RTSP `rtsp://192.168.42.1/live` (Sphinx: `10.202.0.1`) via Pdraw/`drone.streaming`; full telemetry event states (battery, GPS, alarms, wifi/cellular) | [V-code: pdraw.py, examples, feature files] |
| 10 | Programmatic camera + flight control | Yes — the union of rows 2/3/4 + media download API (`olympe.Media`, replay URLs, drone web API) | [V + V-code] |
| 11 | Olympe / AirSDK / Sphinx status | Olympe 8.4.0 (2026-05-20), BSD-3, **Linux x86_64 only, Python 3.9–3.11** (wheel tag `manylinux_2_31_x86_64`); AirSDK = onboard missions (Python flight-supervisor + C++/Python guidance), airsdk-cli with self-signed keys, install via drone HTTP; Sphinx 2.25.2 = **real firmware-in-the-loop**, Ubuntu 20/22/24 + NVIDIA GPU (spot-verified by lead session), UE 4.26/5.3 + Gazebo 11 | [V] |
| 12 | Onboard/edge/offboard CV | Onboard: AirSDK missions possible but heavy for this team (cross-compile, reboot-per-install); practical: ground-station CV off the RTSP stream | [V: AirSDK docs] [I] |
| 13 | Manual override via SkyController 4 | **Yes, modal:** SkyController is default piloting source; Olympe must claim source via `CoPiloting.setPilotingSource` (disables sticks); auto-reverts to SkyController on program disconnect. Not blended | [V: copiloting docs + forum 13104] |
| 14 | Link-loss / failsafes | Full RTH suite: preferred home type, custom location, ending behavior (land/hover), min altitude, **auto-RTH delay after disconnection**, auto-trigger mode; cylinder geofence (`geofence.SetMode/SetMaxDistance/SetMaxAltitude`) | [V: rth docs + V-code: geofence.proto] |
| 15 | Adapter architecture feasibility | Strong: Olympe is a clean async Python SDK; **the sim↔real switch is an IP address** — one adapter serves Sphinx and the physical drone | [V: examples] [I] |

## 3. Photography capability vs the MVP shot list

Every MVP shot primitive maps to verified API surface: bracketed stills (native 3/5/7), gimbal pitch control, speed-bounded moves for orbit waypoint rings, RTH, media download. **No orbit primitive exists** — the executor synthesizes orbits as waypoint rings + heading/gimbal pointing (same portable form the PX4 backend needs anyway), with `onboard_tracker`/`auto_look_at` as a post-MVP framing assist. Panorama: ANAFI Ai exposes `start_super_wide_photo_panorama` (091a) — optional later. [V-code + I]

## 4. Gaps and design-arounds

1. Classic `ardrone3.moveTo` support strings omit ANAFI Ai — use `move.extended_move_to`; verify classic in Sphinx anyway (support annotations are known to lag; e.g., gimbal pages list only older models yet the Ai has a gimbal). [V-code + I]
2. No follow-me; tracking via onboard_tracker/auto_look_at [V-code] — post-MVP.
3. OA behavior during scripted moves undocumented [OQ] — Sphinx test; also note OA alert can freeze the drone until OA is disabled [V: OA docs] — handle in executor fault logic.
4. Manual override is modal (piloting-source switch), not blended [V] — the abort path must (a) stop dispatch, (b) release piloting source, (c) rely on auto-reversion on disconnect; physical verification required at Gate G5.
5. Indoor autonomy officially impossible [V] — deferred (doc 01 C18).
6. Olympe = Linux x86_64 only [V] — the team needs one Ubuntu box (Gate G2); Docker-on-Mac is not viable for drone WiFi (no host networking on macOS [I]; no official image [V: forum 16369]).
7. Firmware frozen at 7.7.1 [V] — features we depend on exist today; the risk is unfixed bugs, not removal. Keep the PX4 exit ramp. [I]

## 5. Sphinx as the ANAFI proof (why the stretch goal is credible)

Sphinx executes the actual ANAFI Ai PC firmware (auto-downloaded from firmware.parrot.com), simulates all cameras (inspectable/recordable via `sphinx-cli camera`), and offers fault injection we need: GPS `out_of_order`, wind gust expressions, battery parameters. [V] Expected but unproven: camera2 photo capture + `olympe.Media` download in-sim [OQ — week-1 spike]. Headless CI unofficial (`--RenderOffScreen` user-confirmed) [V: forum 14643].

## 6. Indoor / GPS-denied — the decisive evidence

FAQ: GPS cannot be disabled; no fix ⇒ RTH impaired, assisted/automated modes unavailable. [V: parrot support] Staff answer (2023, unchanged since): no velocity or relative-position control indoors — manual-rate only. [V: forum 19432] No community project found that achieves autonomous indoor ANAFI Ai flight through supported APIs. [I from community scan] ⇒ Indoor autonomy is a platform limit, not an engineering gap we can close this year.

## 7. Community bridges worth knowing

`anafi_ros` + `anafi_autonomy` (Andriy Sarabakha, BSD-3, ROS2 Humble→Jazzy/Kilted, maintained 2025) — credible reference or integration layer if a ROS2 path ever matters [V]; `qgc-mavlink-converter` (mgr098) for QGC-plan→Parrot-FlightPlan format reference [V: listing]; olympe-dockerfile community images [V: listing]. Ecosystem is thin but sufficient. [I]

## 8. Verdict: CONDITIONAL GO

The ANAFI Ai supports the outdoor photography MVP through supported, code-verified APIs, with a high-fidelity simulator to prove everything first. Conditions:

- **C1 (Gate G2) — SATISFIED 2026-08-14:** Mike's Clevo/Sager NH58AF (RTX 2070 Mobile, Ryzen 7 3800XT 8c, 32 GB, 2 TB, dual-boot Linux) meets Sphinx recommended-GPU spec. Residual M0 checks: Ubuntu 20/22/24 on the Linux partition, Secure Boot off, NVIDIA proprietary drivers.
- **C2:** week-1 Sphinx spikes pass — camera2 capture + media download in-sim; extended_move_to behavior; OA interplay.
- **C3:** backend-neutral core preserved so the PX4 exit ramp stays real (custom aircraft only via Gate G3 if evidence forces it — see doc 07).
- **C4:** physical flight only after the identical mission passes on Sphinx, under Gate G5 conditions (Part 107 holder, VLOS, private property, manual override armed, conservative envelope).
- **C5:** no indoor-autonomy commitments anywhere in the MVP narrative.

**What would flip this to NO-GO:** Sphinx spikes revealing that camera2/media or extended_move_to don't work in-sim as documented; Parrot removing ANAFI Ai from SDK support; inability to source any Linux machine. Each triggers re-evaluation at the affected gate rather than silent scope drift.
