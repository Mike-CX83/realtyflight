# 07 — Custom Hardware Options

**Status:** v0.5 framing — 2026-08-14. Full costing deferred deliberately: the ANAFI Ai assessment (doc 06) is **conditional go**, so no aircraft purchase is proposed now. This document defines the exit ramp so Gate G3 (doc 10) is a prepared decision, not a scramble. Per operating constraints, nothing here is a purchase recommendation.

---

## 1. Decision posture

The owned ANAFI Ai remains the default physical platform. A custom build becomes relevant only if a gate trips:

- G2 fails (no Linux/NVIDIA machine obtainable) *and* the team still wants physical flight — note a custom PX4 aircraft **also** needs a Linux ground/dev machine, so this alone doesn't justify a build.
- Sphinx spikes (06 §8 C2) reveal a blocking API gap on the ANAFI path.
- Post-MVP requirements arrive that the ANAFI cannot meet (external localization input for indoor work, onboard companion compute, swappable cameras).

## 2. What a custom path would actually solve (mapped to ANAFI limitations)

| ANAFI Ai limitation (evidence in doc 06) | Custom-build component that solves it |
|---|---|
| No external position input; no GPS-denied guided control | PX4 FC accepting external vision odometry (e.g., companion + RTAB-Map) — the *only* path to indoor autonomy, and a full second project |
| Closed onboard compute (AirSDK sandbox only) | Companion computer (Pi 5 / Jetson class) with full control |
| Fixed camera | Interchangeable payload (gimbal + camera of choice) |
| Maintenance-mode consumer firmware | Community-governed PX4 mainline (BSD-3) |
| Modal manual-override semantics | Standard RC + PX4 offboard/RC priority semantics |

What it does **not** solve: photography quality per dollar (the ANAFI's integrated 48 MP camera + gimbal is hard to match cheaply), regulatory posture, or any MVP requirement — the MVP is simulator-based.

## 3. Reference configurations (indicative, unpriced-committed; validate at gate time)

- **Config A — "PX4 dev-kit class":** ~$600–1,100. Holybro X500 V2 class frame kit + Pixhawk 6C, M10 GPS, telemetry radio, RC (ELRS/FrSky), basic gimbal + small camera OR fixed camera. Solves: PX4 physical target matching our primary sim path 1:1. Doesn't solve: pro photo quality.
- **Config B — "photography-capable PX4":** ~$1,500–3,000+. Config A + 3-axis brushless gimbal (Gremsy-lite/SIYI class) + better camera (SIYI A8/ZR10 class or mirrorless-lite) + companion computer. Solves: full-control photography platform. Cost/effort large; only justified post-capstone.
- **Config C — companion-augmented ANAFI (not a build):** keep ANAFI Ai; add ground-station GPU only. This is effectively Gate G2 hardware and covers every MVP need.

## 4. Cost-of-change insurance already in the architecture

The `DroneBackend` contract + backend-neutral `MissionPlan` mean a future airframe swap touches one adapter, not the mission/safety/UI layers. The PX4 SITL backend we build for the MVP *is* the software half of any future custom aircraft. This is deliberate.

## 5. Gate G3 decision inputs (to be filled if triggered)

Trigger cause; capability gap statement; candidate config quotes (3 vendors); build vs buy-used comparison; Part 107/Remote ID compliance plan for the new airframe; schedule impact; who assembles/tunes; disposal of ANAFI path. Until a trigger, this section intentionally stays empty.
