"""Smoke flight against a live PX4 SITL — the D6 hello-world.

1) Start the simulator (Docker Desktop must be running):

       docker run --rm -it jonasvautherin/px4-gazebo-headless:1.17.0

   (If MAVSDK never connects on a Mac, the container may need your host IP:
    `docker run --rm -it jonasvautherin/px4-gazebo-headless:1.17.0 -v gz_x500 <your-mac-ip>`)

2) In another terminal, inside the venv:

       python -m backends.px4_mavsdk.smoke

Flies: connect -> preflight -> takeoff 10 m -> 30 m box leg -> synthetic photo
-> RTL -> land, printing telemetry evidence at each step. No LLM, no mission
engine — this isolates ONLY the adapter, which is what a smoke test is for.
"""

from __future__ import annotations

import asyncio
import time

from backends.px4_mavsdk import PX4Backend, PX4Config
from core.geo import distance_m
from core.schema import CaptureSpec, GeoPoint


async def main() -> None:
    clock = time.time
    backend = PX4Backend(clock, PX4Config())
    print("connecting to SITL (udp :14540)... start the Docker container if this hangs")
    await backend.connect()
    print("connected.")

    pre = await backend.preflight()
    for item in pre.items:
        print(f"  preflight[{'ok ' if item.ok else 'FAIL'}] {item.name} {item.detail}")
    if not pre.ok:
        print("waiting 10 s for GPS/home to settle, then retrying preflight once...")
        await asyncio.sleep(10)
        pre = await backend.preflight()
        if not pre.ok:
            print("preflight failed — is the sim fully booted?")
            return

    tel = await backend.latest_telemetry()
    start = tel.position
    print(f"home: ({start.lat:.6f},{start.lon:.6f})  battery {tel.battery_pct:.0f}%")

    print("takeoff to 10 m...")
    await backend.takeoff(10.0, idem="smoke:takeoff")
    tel = await backend.latest_telemetry()
    print(f"  alt evidence: {tel.alt_rel_m:.1f} m")

    target = GeoPoint(lat=start.lat + 0.00027, lon=start.lon)  # ~30 m north
    print("goto ~30 m north...")
    await backend.goto(target, 10.0, 4.0, None, idem="smoke:leg1")
    tel = await backend.latest_telemetry()
    print(f"  arrival evidence: {distance_m(tel.position, target):.1f} m from target")

    print("capture (synthetic evidence photo)...")
    ref = await backend.capture_photo(
        CaptureSpec(mode="single", tag="smoke_test"), idem="smoke:cap"
    )
    print(f"  media: {ref.path}")

    print("return to launch...")
    await backend.return_home(idem="smoke:rtl")
    print("land...")
    await backend.land(idem="smoke:land")
    tel = await backend.latest_telemetry()
    print(f"  on ground: in_air={tel.in_air}, alt={tel.alt_rel_m:.2f} m")
    print("\nSMOKE FLIGHT COMPLETE — the adapter speaks PX4.")
    await backend.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
