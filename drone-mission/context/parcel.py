"""Parcel boundary lookup: point → the real lot polygon (doc 13 §2).

v1 provider: any ArcGIS FeatureServer layer with parcel polygons, queried with
the standard esri point-intersect REST call. County-by-county free endpoints
are the capstone answer (Tulsa County's assessor exposes one — the exact URL
is a 10-minute dev-tools errand on the Mac, doc 13 §2, then set
PARCEL_SERVICE_URL). The provider is deliberately generic: any county that
speaks esri JSON is one env var away.

Iron rule: the parcel is a PROPOSAL for the operator's confirm screen. The
validator (GEO-01/02/03 and friends) judges whatever the human ratifies.
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from context.geocode import TIMEOUT_S, USER_AGENT, LookupFailed
from core.schema import GeoPoint

QUERY = (
    "{service}/query?geometry={lon},{lat}&geometryType=esriGeometryPoint"
    "&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*"
    "&returnGeometry=true&outSR=4326&f=json"
)


@dataclass(frozen=True)
class ParcelResult:
    ring: list[GeoPoint]                 # exterior ring, closing duplicate removed
    attributes: dict = field(default_factory=dict)
    source_url: str = ""


def _default_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310
        return resp.read().decode("utf-8")


class ArcGISParcelProvider:
    """Point-in-parcel lookup against one esri FeatureServer layer URL."""

    def __init__(self, service_url: str, *, fetch=None) -> None:
        self.service_url = service_url.rstrip("/")
        self._fetch = fetch or _default_fetch

    async def parcel_at(self, lat: float, lon: float) -> ParcelResult:
        url = QUERY.format(
            service=self.service_url,
            lon=urllib.parse.quote(f"{lon:.8f}"),
            lat=urllib.parse.quote(f"{lat:.8f}"),
        )
        try:
            data = json.loads(await asyncio.to_thread(self._fetch, url))
        except Exception as exc:
            raise LookupFailed(f"parcel service unreachable: {exc}") from exc
        if "error" in data:
            raise LookupFailed(f"parcel service error: {data['error']}")
        features = data.get("features") or []
        if not features:
            raise LookupFailed("no parcel found at that point")
        feat = features[0]
        rings = (feat.get("geometry") or {}).get("rings") or []
        if not rings or len(rings[0]) < 4:
            raise LookupFailed("parcel feature has no usable polygon ring")
        raw = rings[0]                                   # exterior ring (esri: first)
        if raw[0] == raw[-1]:
            raw = raw[:-1]                               # drop the closing duplicate
        ring = [GeoPoint(lat=float(y), lon=float(x)) for x, y in raw]
        return ParcelResult(
            ring=ring,
            attributes=dict(feat.get("attributes") or {}),
            source_url=url,
        )
