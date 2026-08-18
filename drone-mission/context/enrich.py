"""Enrichment orchestrator (D13): address string → PropertyProposal.

Pipeline: geocode (Census) → parcel polygon (county provider) → fit to OUR
schema (≤64 vertices, home point guaranteed inside) → optional TRANSLATION for
sim flights: the real parcel's exact SHAPE is moved so its centroid sits at the
simulator's location — "this is 123 Main St's actual lot, flown in the sim."
Real-world coordinates always survive in the provenance record.

Iron rule, again, because it is the thesis: this produces a PROPOSAL. It lands
on the operator's confirmation screen; the validator judges the ratified plan
with the same 14 rules as ever. Enrichment widens context, never authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely.geometry import Polygon

from context.geocode import GeocodeResult, LookupFailed, geocode
from core.schema import GeoPoint, Property

MAX_VERTICES = 64            # Property.boundary schema cap
M_PER_DEG_LAT = 111_195.0


@dataclass(frozen=True)
class PropertyProposal:
    property: Property
    provenance: dict = field(default_factory=dict)


def _m_per_deg_lon(lat: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat))


def _simplify_ring(ring: list[GeoPoint], lat0: float) -> tuple[list[GeoPoint], float]:
    """Reduce a parcel ring to the schema's vertex cap, gently: start at ~30 cm
    tolerance and widen until it fits. Returns (ring, tolerance_m_used)."""
    poly = Polygon([(p.lon, p.lat) for p in ring])
    if not poly.is_valid:
        poly = poly.buffer(0)            # standard self-touch repair
        if poly.geom_type != "Polygon" or not poly.is_valid:
            raise LookupFailed("parcel polygon is invalid and unrepairable")
    tol_m = 0.0
    while True:
        coords = list(poly.exterior.coords)[:-1]
        if 3 <= len(coords) <= MAX_VERTICES:
            return [GeoPoint(lat=y, lon=x) for x, y in coords], tol_m
        tol_m = 0.3 if tol_m == 0.0 else tol_m * 2.0
        if tol_m > 50.0:
            raise LookupFailed("parcel polygon would not simplify to 64 vertices")
        poly = Polygon([(p.lon, p.lat) for p in ring]).simplify(
            tol_m / _m_per_deg_lon(lat0), preserve_topology=True
        )


def _translate(ring: list[GeoPoint], home: GeoPoint, center: GeoPoint,
               new_center: GeoPoint) -> tuple[list[GeoPoint], GeoPoint, GeoPoint]:
    """Move the parcel's exact shape so its centroid sits at new_center —
    meters-preserving in the local frame (sim flights fly the REAL lot shape)."""
    lat0, lat1 = center.lat, new_center.lat
    dn_m = (new_center.lat - center.lat) * M_PER_DEG_LAT
    de_m = (new_center.lon - center.lon) * _m_per_deg_lon(lat0)

    def shift(p: GeoPoint) -> GeoPoint:
        north_m = (p.lat - center.lat) * M_PER_DEG_LAT
        east_m = (p.lon - center.lon) * _m_per_deg_lon(lat0)
        return GeoPoint(
            lat=new_center.lat + north_m / M_PER_DEG_LAT,
            lon=new_center.lon + east_m / _m_per_deg_lon(lat1),
        )

    _ = (dn_m, de_m)  # provenance callers may want these later
    return [shift(p) for p in ring], shift(home), new_center


async def propose_property(
    address: str,
    *,
    provider=None,
    translate_center: GeoPoint | None = None,
    geocoder=geocode,
) -> PropertyProposal:
    """address → PropertyProposal. Raises LookupFailed with an operator-facing
    message on any miss; never returns a half-guessed boundary silently.

    provider=None -> geocode-only fallback: a modest 60x60 m square around the
    matched point, honestly labeled boundary_source='geocode-fallback-square'.
    """
    geo: GeocodeResult = await geocoder(address)
    provenance: dict = {
        "address_input": address,
        "address_matched": geo.matched_address,
        "geocode_source": geo.source_url,
        "real_lat": geo.lat,
        "real_lon": geo.lon,
        "translated": False,
    }

    if provider is not None:
        parcel = await provider.parcel_at(geo.lat, geo.lon)
        ring, tol_m = _simplify_ring(parcel.ring, geo.lat)
        provenance.update(
            boundary_source="county-parcel",
            parcel_source=parcel.source_url,
            parcel_vertices_raw=len(parcel.ring),
            parcel_vertices_used=len(ring),
            simplify_tolerance_m=round(tol_m, 2),
        )
    else:
        half = 30.0 / M_PER_DEG_LAT
        half_lon = 30.0 / _m_per_deg_lon(geo.lat)
        ring = [
            GeoPoint(lat=geo.lat - half, lon=geo.lon - half_lon),
            GeoPoint(lat=geo.lat - half, lon=geo.lon + half_lon),
            GeoPoint(lat=geo.lat + half, lon=geo.lon + half_lon),
            GeoPoint(lat=geo.lat + half, lon=geo.lon - half_lon),
        ]
        provenance["boundary_source"] = "geocode-fallback-square"

    poly = Polygon([(p.lon, p.lat) for p in ring])
    rp = poly.representative_point()             # guaranteed INSIDE (GEO-02)
    home = GeoPoint(lat=rp.y, lon=rp.x)
    c = poly.centroid
    center = GeoPoint(lat=c.y, lon=c.x)

    if translate_center is not None:
        ring, home, center = _translate(ring, home, center, translate_center)
        provenance["translated"] = True
        provenance["sim_center"] = {
            "lat": translate_center.lat, "lon": translate_center.lon
        }

    return PropertyProposal(
        property=Property(center=center, boundary=ring, home=home),
        provenance=provenance,
    )
