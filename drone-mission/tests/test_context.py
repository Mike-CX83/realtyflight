"""D13 context-enrichment tests: address → geocode → parcel → PropertyProposal.

Network policy: unit tests run on RECORDED fixtures (the Census fixture is the
real response shape verified live 2026-08-18; the esri fixture matches the
documented FeatureServer JSON). One live integration test exists behind
RUN_LIVE_CONTEXT=1 for machines with real internet (the Mac).

Doctrine under test everywhere: enrichment produces PROPOSALS that fit OUR
schema (≤64 vertices, home strictly inside) — the validator stays the judge.
"""

from __future__ import annotations

import json
import math
import os

import pytest
from shapely.geometry import Polygon

from context import (
    ArcGISParcelProvider,
    LookupFailed,
    geocode,
    propose_property,
)
from core.schema import GeoPoint

# ---- recorded fixture: US Census onelineaddress (live-verified shape) ------ #

CENSUS_HIT = json.dumps({
    "result": {
        "addressMatches": [
            {
                "matchedAddress": "175 E 2ND ST, TULSA, OK, 74103",
                "coordinates": {"x": -95.989531064219, "y": 36.155124507955},
            }
        ]
    }
})
CENSUS_MISS = json.dumps({"result": {"addressMatches": []}})


def _fetch_returning(payload: str):
    def fetch(url: str) -> str:
        return payload
    return fetch


async def test_geocode_parses_the_census_shape():
    r = await geocode("175 E 2nd St, Tulsa, OK", fetch=_fetch_returning(CENSUS_HIT))
    assert r.matched_address.startswith("175 E 2ND ST")
    assert abs(r.lat - 36.155124) < 1e-4 and abs(r.lon - -95.989531) < 1e-4


async def test_geocode_no_match_is_a_typed_operator_facing_failure():
    with pytest.raises(LookupFailed) as exc:
        await geocode("123 Nowhere Ln, Atlantis", fetch=_fetch_returning(CENSUS_MISS))
    assert "no address match" in str(exc.value)


async def test_geocode_garbage_reply_is_typed_not_a_crash():
    with pytest.raises(LookupFailed):
        await geocode("x", fetch=_fetch_returning("<html>maintenance</html>"))


# ---- recorded fixture: esri FeatureServer point-intersect ------------------ #

def _esri_square(lat: float, lon: float, half_m: float = 40.0) -> str:
    dlat = half_m / 111_195.0
    dlon = half_m / (111_195.0 * math.cos(math.radians(lat)))
    ring = [
        [lon - dlon, lat - dlat], [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat], [lon - dlon, lat + dlat],
        [lon - dlon, lat - dlat],                       # esri rings close
    ]
    return json.dumps({
        "spatialReference": {"wkid": 4326},
        "features": [{
            "attributes": {"PARCEL_ID": "TU-12345", "OWNER": "recorded-fixture"},
            "geometry": {"rings": [ring]},
        }],
    })


async def test_arcgis_provider_parses_ring_and_drops_closing_duplicate():
    p = ArcGISParcelProvider(
        "https://example.test/FeatureServer/0",
        fetch=_fetch_returning(_esri_square(36.1551, -95.9895)),
    )
    res = await p.parcel_at(36.1551, -95.9895)
    assert len(res.ring) == 4                            # closing dup removed
    assert res.attributes["PARCEL_ID"] == "TU-12345"


async def test_arcgis_provider_no_feature_is_typed():
    p = ArcGISParcelProvider(
        "https://example.test/FeatureServer/0",
        fetch=_fetch_returning(json.dumps({"features": []})),
    )
    with pytest.raises(LookupFailed):
        await p.parcel_at(36.0, -95.0)


async def test_arcgis_provider_service_error_is_typed():
    p = ArcGISParcelProvider(
        "https://example.test/FeatureServer/0",
        fetch=_fetch_returning(json.dumps({"error": {"code": 400, "message": "bad"}})),
    )
    with pytest.raises(LookupFailed):
        await p.parcel_at(36.0, -95.0)


# ---- enrichment: schema fit, home inside, translation ---------------------- #

class _RingProvider:
    """Fake provider: a 200-vertex near-circle parcel (stress the 64-vertex cap)."""

    def __init__(self, lat: float, lon: float, r_m: float = 45.0, n: int = 200):
        self.ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            self.ring.append(GeoPoint(
                lat=lat + (r_m * math.cos(a)) / 111_195.0,
                lon=lon + (r_m * math.sin(a)) / (111_195.0 * math.cos(math.radians(lat))),
            ))

    async def parcel_at(self, lat, lon):
        from context.parcel import ParcelResult
        return ParcelResult(ring=self.ring, attributes={}, source_url="fake://parcel")


async def _census_geocoder(address: str):
    return await geocode(address, fetch=_fetch_returning(CENSUS_HIT))


async def test_proposal_fits_schema_and_home_is_inside():
    prov = _RingProvider(36.155124, -95.989531)
    prop = await propose_property(
        "175 E 2nd St, Tulsa, OK", provider=prov, geocoder=_census_geocoder
    )
    b = prop.property.boundary
    assert 3 <= len(b) <= 64, "boundary must fit the MissionPlan schema cap"
    from shapely.geometry import Point

    poly = Polygon([(p.lon, p.lat) for p in b])
    assert poly.contains(Point(prop.property.home.lon, prop.property.home.lat)), (
        "home must be STRICTLY inside the proposed boundary (GEO-02 feeds on this)"
    )
    assert prop.provenance["boundary_source"] == "county-parcel"
    assert prop.provenance["parcel_vertices_raw"] == 200
    assert prop.provenance["parcel_vertices_used"] <= 64


async def test_translation_moves_the_real_shape_to_the_sim():
    """Sim mode: the REAL parcel shape is flown at the simulator's location —
    edge lengths preserved within 1%, real coords kept in provenance, and
    (D13.1, the agent's ~50 m RTL finding) plan.home lands EXACTLY on the sim
    position: PX4's RTL-to-launch and the plan's home are the same point."""
    prov = _RingProvider(36.155124, -95.989531)
    sim_home = GeoPoint(lat=47.397742, lon=8.545594)     # PX4 SITL Zurich
    prop = await propose_property(
        "175 E 2nd St, Tulsa, OK", provider=prov,
        translate_center=sim_home, geocoder=_census_geocoder,
    )
    from shapely.geometry import Point

    h = prop.property.home
    assert abs(h.lat - sim_home.lat) < 1e-9 and abs(h.lon - sim_home.lon) < 1e-9, (
        "home must be ANCHORED to the sim launch point — RTL returns there"
    )
    poly = Polygon([(p.lon, p.lat) for p in prop.property.boundary])
    assert poly.contains(Point(h.lon, h.lat))            # still strictly inside

    def edge_m(a: GeoPoint, b: GeoPoint, lat0: float) -> float:
        dn = (a.lat - b.lat) * 111_195.0
        de = (a.lon - b.lon) * 111_195.0 * math.cos(math.radians(lat0))
        return math.hypot(dn, de)

    orig = await propose_property(
        "175 E 2nd St, Tulsa, OK", provider=prov, geocoder=_census_geocoder
    )
    ob, tb = orig.property.boundary, prop.property.boundary
    assert len(ob) == len(tb)
    for i in range(len(ob)):
        e0 = edge_m(ob[i], ob[(i + 1) % len(ob)], 36.155)
        e1 = edge_m(tb[i], tb[(i + 1) % len(tb)], 47.398)
        assert abs(e0 - e1) <= max(0.5, 0.01 * e0), f"edge {i} distorted: {e0} vs {e1}"
    assert prop.provenance["translated"] is True
    assert abs(prop.provenance["real_lat"] - 36.155124) < 1e-4  # truth preserved


async def test_geocode_only_fallback_square_is_honestly_labeled():
    prop = await propose_property(
        "175 E 2nd St, Tulsa, OK", provider=None, geocoder=_census_geocoder
    )
    assert len(prop.property.boundary) == 4
    assert prop.provenance["boundary_source"] == "geocode-fallback-square"


# ---- live integration (Mac / real internet only) ---------------------------- #

@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_CONTEXT"),
    reason="set RUN_LIVE_CONTEXT=1 with real internet to hit the live geocoder",
)
async def test_live_census_geocoder_round_trip():
    r = await geocode("175 E 2nd St, Tulsa, OK")
    assert abs(r.lat - 36.1551) < 0.01 and abs(r.lon + 95.9895) < 0.01
