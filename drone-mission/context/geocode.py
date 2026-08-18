"""Address → lat/lon via the US Census Geocoder (doc 13 §1 — VERIFIED live:
free, keyless, public domain; re-verified from the build session 2026-08-18,
field paths result.addressMatches[0].coordinates.x/.y).

Design notes:
- stdlib urllib in a worker thread: zero new runtime dependencies.
- Typed failure (LookupFailed) at this boundary; callers translate it into a
  clean HTTP error or an honest "couldn't find that address" — never a 500.
- The injected `fetch` hook exists for tests (recorded fixtures) and for any
  future transport swap; production uses the default.
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

CENSUS_URL = (
    "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    "?address={address}&benchmark=Public_AR_Current&format=json"
)
TIMEOUT_S = 10.0
USER_AGENT = "RealtyFlight-capstone/1.0 (student project)"


class LookupFailed(Exception):
    """Typed enrichment failure: no match, bad response, or network trouble.
    The message is operator-facing — say what happened plainly."""


@dataclass(frozen=True)
class GeocodeResult:
    matched_address: str
    lat: float
    lon: float
    source_url: str


def _default_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310
        return resp.read().decode("utf-8")


async def geocode(address: str, *, fetch=None) -> GeocodeResult:
    address = address.strip()
    if not address:
        raise LookupFailed("empty address")
    url = CENSUS_URL.format(address=urllib.parse.quote(address))
    fetcher = fetch or _default_fetch
    try:
        raw = await asyncio.to_thread(fetcher, url)
        data = json.loads(raw)
        matches = data["result"]["addressMatches"]
    except LookupFailed:
        raise
    except Exception as exc:
        raise LookupFailed(f"geocoder unreachable or malformed reply: {exc}") from exc
    if not matches:
        raise LookupFailed(f"no address match for {address!r} — check spelling/ZIP")
    m = matches[0]
    try:
        return GeocodeResult(
            matched_address=str(m["matchedAddress"]),
            lat=float(m["coordinates"]["y"]),
            lon=float(m["coordinates"]["x"]),
            source_url=url,
        )
    except Exception as exc:
        raise LookupFailed(f"geocoder reply missing fields: {exc}") from exc
