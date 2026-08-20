"""Export a recorded mission as showcase-replay JSON (D13 showcase).

The public showcase page (showcase/index.html) replays a mission from its
append-only audit log plus the photo sidecars' telemetry. This tool builds
that JSON from the real artifacts — nothing is hand-animated.

Usage (from drone-mission/):
  python -m demo.export_replay DASH-20260818-193332-adb1 \
      --label "Real-parcel mission — 305 S Kenosha Ave" \
      --address "305 S Kenosha Ave, Tulsa, OK" \
      --home 47.397742,8.545594 \
      --inject ../showcase/index.html

  # add more missions with repeated invocations using --merge, or export raw:
  python -m demo.export_replay <mission_id> --out replay.json

--address (optional, needs internet + .phone_demo.env's DASH_PARCEL_URL):
re-derives the SAME translated parcel boundary the mission flew (geocode →
county parcel → home-anchored translation, D13.1) and embeds it so the replay
draws the real lot outline.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import re
import sqlite3
from pathlib import Path

SLIM_TRIM = {"items", "messages"}


def _events(db: sqlite3.Connection, mission_id: str) -> list[dict]:
    rows = db.execute(
        "SELECT ts, type, payload FROM mission_events WHERE mission_id=? ORDER BY seq",
        (mission_id,),
    ).fetchall()
    if not rows:
        raise SystemExit(f"no events for mission {mission_id!r}")
    out = []
    for ts, ty, payload in rows:
        p = {k: v for k, v in json.loads(payload).items() if k not in SLIM_TRIM}
        if ty == "plan.proposed":
            p["request_text"] = str(p.get("request_text", ""))[:160]
            p["summary"] = str(p.get("summary", ""))[:200]
        out.append({"ts": ts, "type": ty, "p": p})
    return out


def _captures(media_dir: str, t0: float, t1: float) -> list[dict]:
    caps = []
    for f in sorted(glob.glob(str(Path(media_dir) / "*.json"))):
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        ts = d.get("ts", 0)
        tel = d.get("telemetry") or {}
        pos = tel.get("position") or {}
        if t0 - 2 <= ts <= t1 + 2 and pos.get("lat") is not None:
            caps.append({
                "ts": ts, "tag": d.get("tag", "photo"),
                "lat": pos["lat"], "lon": pos["lon"],
                "alt": float(tel.get("alt_rel_m") or 0.0),
            })
    caps.sort(key=lambda c: c["ts"])
    return caps


def _parcel_url() -> str | None:
    env = Path(".phone_demo.env")
    if env.exists():
        m = re.search(r'DASH_PARCEL_URL="?([^"\n]+)"?', env.read_text())
        return m.group(1).strip() if m else None
    return None


async def _boundary(address: str, home_lat: float, home_lon: float) -> list[dict] | None:
    from context import ArcGISParcelProvider, propose_property
    from core.schema import GeoPoint

    url = _parcel_url()
    provider = ArcGISParcelProvider(url) if url else None
    prop = await propose_property(
        address, provider=provider,
        translate_center=GeoPoint(lat=home_lat, lon=home_lon),
    )
    return [{"lat": p.lat, "lon": p.lon} for p in prop.property.boundary]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mission_id")
    ap.add_argument("--db", default="runs/mission_events.sqlite3")
    ap.add_argument("--media", default="media")
    ap.add_argument("--label", default=None)
    ap.add_argument("--key", default="hero", help="slot name in the page (hero/abort/…)")
    ap.add_argument("--address", default=None, help="re-derive the flown parcel boundary")
    ap.add_argument("--home", default="47.397742,8.545594",
                    help="launch lat,lon the mission was anchored to (D13.1)")
    ap.add_argument("--out", default=None, help="write standalone JSON here")
    ap.add_argument("--inject", default=None,
                    help="path to showcase/index.html — replace its embedded data slot")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    events = _events(db, args.mission_id)
    t0, t1 = events[0]["ts"], events[-1]["ts"]
    closed = next((e["p"] for e in reversed(events) if e["type"] == "mission.closed"), {})
    caps = _captures(args.media, t0, t1)
    home_lat, home_lon = (float(x) for x in args.home.split(","))

    boundary = None
    if args.address:
        boundary = asyncio.run(_boundary(args.address, home_lat, home_lon))

    mission = {
        "label": args.label or args.mission_id,
        "outcome": closed.get("outcome", "?"),
        "photos": closed.get("media_count", len(caps)),
        "events": events,
        "captures": caps,
        "boundary": boundary,
    }

    if args.inject:
        page = Path(args.inject)
        html = page.read_text()
        m = re.search(
            r'(<script type="application/json" id="replay-data">)(.*?)(</script>)',
            html, re.DOTALL,
        )
        if not m:
            raise SystemExit("no replay-data slot found in the page")
        data = json.loads(m.group(2))
        data.setdefault("missions", {})[args.key] = mission
        data.setdefault("home", {"lat": home_lat, "lon": home_lon})
        html = html[: m.start(2)] + json.dumps(data, separators=(",", ":")) + html[m.end(2):]
        page.write_text(html)
        print(f"injected {args.mission_id} into {page} as '{args.key}' "
              f"({len(events)} events, {len(caps)} captures, "
              f"boundary={'yes' if boundary else 'no'})")
    if args.out:
        Path(args.out).write_text(json.dumps(mission, indent=1))
        print(f"wrote {args.out}")
    if not args.inject and not args.out:
        print(json.dumps(mission)[:400] + " …  (use --out or --inject)")


if __name__ == "__main__":
    main()
