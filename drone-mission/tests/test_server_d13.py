"""D13 server tests: the address-lookup flow over HTTP.

- /api/lookup sits behind the same token wall as everything else
- a successful lookup returns the matched address + a boundary the page can
  draw, stores the proposal, and audits lookup.performed
- planning with use_looked_up flies THAT boundary (the validator judged it —
  GEO rules ran against the real parcel, and the flight completes inside it)
- use_looked_up without a lookup is a 409, and a failed lookup is a clean
  ok:false, never a 500
- doctrine: the lookup NEVER auto-plans or auto-approves anything
"""

from __future__ import annotations

import math

from context.enrich import PropertyProposal
from core.schema import GeoPoint, Property
from tests.test_server import auth, dash, wait_state
from tests.test_server_d12 import _approve_body

FAKE_HOME = GeoPoint(lat=36.15360, lon=-95.99320)      # FakeBackend's home


def _proposal_near(center: GeoPoint, half_m: float = 70.0) -> PropertyProposal:
    dlat = half_m / 111_195.0
    dlon = half_m / (111_195.0 * math.cos(math.radians(center.lat)))
    ring = [
        GeoPoint(lat=center.lat - dlat, lon=center.lon - dlon),
        GeoPoint(lat=center.lat - dlat, lon=center.lon + dlon),
        GeoPoint(lat=center.lat + dlat, lon=center.lon + dlon),
        GeoPoint(lat=center.lat + dlat, lon=center.lon - dlon),
    ]
    return PropertyProposal(
        property=Property(center=center, boundary=ring, home=center),
        provenance={
            "address_matched": "175 E 2ND ST, TULSA, OK, 74103",
            "boundary_source": "county-parcel",
            "translated": True,
            "real_lat": 36.155124, "real_lon": -95.989531,
        },
    )


def _patch_lookup(monkeypatch, proposal=None, error: str | None = None):
    from context.geocode import LookupFailed

    async def fake_propose(address, *, provider=None, translate_center=None,
                           geocoder=None):
        if error:
            raise LookupFailed(error)
        return proposal

    monkeypatch.setattr("server.app.propose_property", fake_propose)


def test_lookup_requires_the_token(tmp_path):
    with dash(tmp_path) as (client, backend):
        r = client.post("/api/lookup",
                        json={"address": "175 E 2nd St, Tulsa, OK", "operator": "m"})
        assert r.status_code == 401


def test_lookup_then_plan_flies_the_real_boundary(tmp_path, monkeypatch):
    with dash(tmp_path) as (client, backend):
        _patch_lookup(monkeypatch, proposal=_proposal_near(FAKE_HOME))

        r = client.post("/api/lookup", headers=auth(),
                        json={"address": "175 E 2nd St, Tulsa, OK", "operator": "mike"})
        assert r.status_code == 200
        lk = r.json()
        assert lk["ok"] is True
        assert lk["matched_address"].startswith("175 E 2ND ST")
        assert len(lk["boundary"]) == 4
        assert lk["provenance"]["boundary_source"] == "county-parcel"

        r = client.post("/api/plan", headers=auth(),
                        json={"request_text": "full exterior package",
                              "operator": "mike", "use_looked_up": True})
        p = r.json()
        assert p["ok"] is True, p
        # THE point of D13: the plan's boundary IS the looked-up parcel,
        # and the geometry rules validated the flight against it.
        assert p["boundary"] == lk["boundary"]
        assert p["property_provenance"]["boundary_source"] == "county-parcel"
        assert any(row["rule"] == "GEO-03" and row["passed"] for row in p["report"])

        r = client.post("/api/approve", headers=auth(), json=_approve_body(p))
        assert r.status_code == 200
        s = wait_state(client, lambda s: s["outcome"] == "completed")
        assert s["photos"] == p["expected_photos"]

        events = client.get(f"/api/replay/{p['mission_id']}", headers=auth()).json()["events"]
        by_type = {e["type"]: e for e in events}
        assert by_type["plan.proposed"]["payload"]["boundary_source"] == "county-parcel"


def test_plan_use_looked_up_without_lookup_is_409(tmp_path):
    with dash(tmp_path) as (client, backend):
        r = client.post("/api/plan", headers=auth(),
                        json={"request_text": "x", "operator": "mike",
                              "use_looked_up": True})
        assert r.status_code == 409


def test_failed_lookup_is_clean_and_stores_nothing(tmp_path, monkeypatch):
    with dash(tmp_path) as (client, backend):
        _patch_lookup(monkeypatch, error="no address match for '123 Nowhere'")
        r = client.post("/api/lookup", headers=auth(),
                        json={"address": "123 Nowhere", "operator": "mike"})
        assert r.status_code == 200
        assert r.json()["ok"] is False
        r = client.post("/api/plan", headers=auth(),
                        json={"request_text": "x", "operator": "mike",
                              "use_looked_up": True})
        assert r.status_code == 409          # nothing was stored by the failure
