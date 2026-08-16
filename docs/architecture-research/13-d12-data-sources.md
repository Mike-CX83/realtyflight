# 13 — D12 Data-Source Spike (address → boundary → context)

**Status:** v1.0 — spike run 2026-08-15 from the Cowork cloud environment.
Evidence labels follow CLAUDE.md: **Verified by running** (actual call + response),
**Located, unconfirmed** (endpoint identified; call blocked by the cloud sandbox's
fetch policy, not by the service — confirm from the Mac), **Documented only**,
**Knowledge** (stable facts; verify at build time).

Iron rule from the D12 TODO block applies to every source below: external data
widens the LLM's **context**, never its **authority**. Every enriched input lands
on a human-confirmation screen; the validator judges the plan against what the
human ratified.

---

## 1. Geocoding: address → lat/lon — ✅ Verified by running

**US Census Geocoder** — free, no API key, public domain, unlimited reasonable use.

```
GET https://geocoding.geo.census.gov/geocoder/locations/onelineaddress
    ?address=175 E 2nd St, Tulsa, OK&benchmark=Public_AR_Current&format=json
→ matched "175 E 2ND ST, TULSA, OK, 74103"
→ lon -95.989531, lat 36.155125
```

Design: this is D12 phase 1's first hop. Fallback: OSM Nominatim (attribution
required, 1 req/s policy — fine for our volume, or self-host).
Fun fact: City Hall geocodes ~100 m from the conftest test property — our sim
neighborhood was downtown Tulsa all along.

## 2. Parcel polygons (the boundary proposal) — 🟡 Located, unconfirmed

- The **official Tulsa County Assessor** runs a public parcel-mapping web app
  (assessor.tulsacounty.org / tulsacounty.org/assessor) with per-parcel pages and
  advertised shapefile/CSV exports — the data clearly exists and is public.
- No public county ArcGIS host answered from the cloud (maps.tulsacounty.org:
  no DNS; INCOG rest root: 404), and the county's AGOL planning service
  (`Tulsa_County_Planning_Web_Map/FeatureServer`) carries boundaries but **no
  parcels layer**.
- **10-minute confirmation from the Mac (agent task):** open the assessor's
  parcel map in a browser with dev-tools → Network tab → the app's tile/feature
  requests expose the real parcel service URL; then
  `curl "<service>/query?geometry=<lon>,<lat>&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=true&outSR=4326&f=json"`
  and confirm a polygon ring returns for the City Hall point above.
- **Productized path (multi-county, later):** Regrid — commercial nationwide
  normalized parcel API. County-by-county free endpoints are the capstone answer;
  Regrid is the company answer. Budget note for docs/09 §5 when the time comes.

## 3. Building footprints (auto-center + orbit sizing) — 🟡 Located, unconfirmed ×2

Two independent paths, either one unlocks "orbit centers itself on the structure":

- **`Buildings_Tulsa_County` FeatureServer** (AGOL,
  `services3.arcgis.com/ratx1xWpTPZDmMzX/.../Buildings_Tulsa_County/FeatureServer/11`)
  — found via search; the point-intersect query was rejected by the *cloud
  sandbox's* proxy, not the server. Same curl recipe as §2 confirms from the Mac.
- **OSM via Overpass** (`overpass-api.de`) — robots-blocked from the cloud
  sandbox; normal API use from the Mac is fine within OSM's usage policy.
  Query: `way(around:30,<lat>,<lon>)[building]; out geom;`
  License: **ODbL** — attribution required; using footprints to position flights
  is fine, but bulk-storing/redistributing derived *databases* triggers
  share-alike. Keep it per-lookup.
- Bulk fallback: Microsoft Global Building Footprints (ODbL, downloadable per
  region) if per-request lookups ever become a bottleneck.

Design: footprint → centroid = proposed `Property.center`; footprint's max
radius + margin = proposed orbit radius. Both land on the confirm screen.

## 4. Satellite tiles for the dashboard map — 📘 Knowledge (verify terms at build)

- **USGS NAIP imagery** — public domain, US-wide aerial (~0.6–1 m), served via
  USGS/ArcGIS endpoints. The safe default for a commercial future.
- **Esri World Imagery** — the pretty default in Leaflet examples; free tier
  requires attribution + an ArcGIS Location Platform key for production use.
- **MapTiler / Mapbox** — free tiers with keys; paid at product volume.
- Plain **OSM raster tiles** are street maps, not satellite — fine for dev,
  wrong look for real estate.
Decision for D11 v1: Leaflet + Esri World Imagery w/ attribution for the demo,
NAIP as the licensing-clean fallback; revisit at commercialization (B5 world).

## 5. MLS / listing data — 📘 Knowledge (access is the constraint, not tech)

- The standard is **RESO Web API**, but access rides on MLS membership/broker
  sponsorship (MLSs gate their feeds; students generally can't get keys).
- **Capstone answer:** the agent pastes the listing text/photos into the
  dashboard (or uploads the MLS sheet PDF) → we extract structured fields
  (pool y/n, acreage, stories…) → planner context. Zero gatekeepers, same value.
- **Company answer (later):** RESO feed via a sponsoring broker — literally the
  realtor-with-an-edge from B5 sponsoring their own toolchain.

## 6. Documents / OCR & photos — 📘 Knowledge, design settled in TODO D12

Vision-capable LLMs read listing photos and PDFs directly (no separate OCR stack
needed at our scale). Both are **advisory-only** inputs by D12's hard rule:
surveys/plats can inform the operator, never define a boundary.

---

## Spike verdict

Phase 1 of D12 (address → proposed boundary → human confirm) is **buildable with
zero paid services**: verified geocoder + county parcels (one confirmation curl
away) + two footprint paths. The only genuinely gated source is MLS, and the
paste-the-listing fallback erases it for the capstone. Next actions live in the
D12 TODO block; the two 🟡 confirmations are a single 15-minute agent errand,
best done alongside the D9/D10 handoffs.
