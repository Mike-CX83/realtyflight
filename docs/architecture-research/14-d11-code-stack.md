# 14 — D11/D12 Open-Source Code Stack (adopt / read / write ourselves)

**Status:** v1.0 — 2026-08-15. Companion to doc 13 (data sources) and the D11/D12
TODO blocks. Evidence labels per CLAUDE.md; licenses re-checked at adoption time.

**The principle:** adopt permissively-licensed commodity layers as dependencies;
*read* restrictively-licensed or architecture-relevant projects as pattern donors
without linking a line of them; and deliberately hand-write the thin governance
layer — because the approval/validation UX **is the capstone thesis**, and it is
small (a few hundred lines) by design.

---

## 1. ADOPT — runtime dependencies (all permissive)

| Piece | Project | License | Evidence | Role |
|---|---|---|---|---|
| API server | FastAPI | MIT | knowledge (stable) | routes: plan / approve / abort / hold / state |
| ASGI server | uvicorn | BSD-3 | knowledge | serves FastAPI + WebSocket |
| Live updates | browser-native WebSocket | built-in | — | telemetry/state push, zero client deps |
| Map | Leaflet | BSD-2 | knowledge | phone-friendly 2D map, tiny footprint |
| Boundary draw/edit | **leaflet-geoman-free** | **MIT — license file read 2026-08-15** | ✅ verified | draw/adjust the property polygon on the confirm screen (D12 §1); actively maintained; the older Leaflet.draw is stale — prefer Geoman |
| GIS/geocoder calls | httpx (or requests) | BSD | knowledge | plain REST to Census/ArcGIS/Overpass — no vendor SDK needed |
| Geometry | shapely, pymap3d | BSD | already in the project | reuse `core/geo.py` — the dashboard adds no new math |
| Schemas | pydantic | MIT | already in the project | plans/telemetry serialize to the browser for free |
| Voice (stretch) | Web Speech API | built into browsers | — | in-app mic; day-one voice is the phone keyboard's dictation, zero code |
| Voice (server fallback, later) | faster-whisper | MIT | knowledge — verify at adoption | if browser STT disappoints on iOS |

Frontend framework: **none** — one hand-written HTML/JS page (matches the D11
spec, the team's maintenance reality, and the "explainable at the defense" bar).
React/Vite is an allowed later refactor, not a v1 dependency.

## 2. READ — pattern donors (never linked, licenses stay at arm's length)

| Project | Where | License posture | What to mine |
|---|---|---|---|
| MDS (mavsdk_drone_show) | already in `research/` | PolyForm — read-only per G1 | its dashboard/telemetry UI layout, ops-console patterns |
| dronesphere | already in `research/` | read-only reference | FastAPI + telemetry endpoint shapes |
| PX4 Flight Review | github.com/PX4/flight_review | BSD-3 (verify) | flight-replay UI: how pros render a mission after the fact — feeds our event-log replay view; could even ingest PX4 ulogs someday |
| MAVCesium | github.com/stephendade/MAVCesium | permissive (verify) | 3D map telemetry presentation ideas (post-MVP flair) |
| QGroundControl | external app | GPL/Apache dual | keep as the side-by-side power tool it already is; never link its code |

## 3. LATER / ADJACENT — flagged so nobody rediscovers them

- **OpenDroneMap / WebODM** (GPL/AGPL): turns our captured photo sets into
  orthomosaics and 3D property models — an enormous future wow for listings.
  License means: run it as an external service/container we call, never linked
  code. Post-capstone (M7+ / B5 product territory).
- **Regrid** (commercial parcels API): the multi-county product path from doc 13.

## 4. WRITE OURSELVES — deliberately (~400–600 lines total)

1. `server/` FastAPI app: ~8 routes + one WebSocket, auth dependency stub
   (shared secret + operator name; the designed swap-point for real accounts+TLS
   per the D11 block), wiring straight into the existing planner/approval/
   executor/event-log — no new engine code.
2. The one dashboard page: intent box → plan + rule-checklist render → APPROVE →
   live map trail → abort/hold/breaker → gallery → replay timeline.
3. D12 §1 adapter: address → geocode → parcel fetch → proposed boundary
   (+ footprint → proposed center/radius), all onto the confirm screen.

Why not adopt a dashboard wholesale: no open project renders *governance* —
typed plans, rule-by-rule verdicts, hash-bound approval, evidence-gated state.
That layer is the thesis, it is small, and it must be explainable line-by-line
at the defense.

## 5. License hygiene (standing rule)

Dependencies: MIT/BSD/Apache only. GPL/AGPL/PolyForm projects are tools we run
or texts we read — never imports. Every adoption gets its license noted in
`pyproject.toml`/README at the moment it lands. This keeps the B5 commercial
path unencumbered.

## 6. Pantry additions (gap scan 2026-08-16 — small free clients, no new frameworks)

| Need (when) | Source | License/terms | Note |
|---|---|---|---|
| Preflight wind advisory (D11+/M7) | NWS API — api.weather.gov | US-gov public domain, keyless | forecast wind at the property on the approval screen, checked against G5 wind limits |
| Airspace awareness (D12+/product) | FAA UAS Facility Maps (open ArcGIS data) | open data | controlled-airspace + LAANC grid ceiling advisory on the confirm screen; actual LAANC auth = commercial USS, company-era |
| Defense-day demo insurance — **EVENTUAL, not now (Mike's call 2026-08-16)** | Ollama + a local model | MIT (Ollama) | deliberately deferred to the Linux/RTX box (A-track), which is the right hardware for local models anyway; revisit at M8 rehearsal — planner is provider-neutral, so wiring it later is a model-string change, zero code |
| EXIF geotagging (M7 media export) | piexif + Pillow | MIT | GPS/attitude into each JPEG's EXIF, not just sidecars — photos drop into MLS/editing tools natively |
| Real auth, when the stub swaps (post-capstone) | fastapi-users | MIT | the designed swap-point in D11's auth dependency |

Verdict of the gap scan: the remaining build (D11–D13, M4–M8) requires **no new
frameworks and no paid dependencies** — only small clients to free public APIs.
The only commercial dependency anywhere on the map stays MLS (fallback: paste
the listing) and, someday, LAANC authorization providers.
