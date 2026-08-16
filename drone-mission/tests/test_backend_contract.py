"""The backend contract suite — ONE set of expectations, every backend.

Runs fully against FakeBackend in CI. Set RUN_PX4_CONTRACT=1 with a live SITL
(docker run --rm -it jonasvautherin/px4-gazebo-headless:1.17.0) and the SAME
tests run against PX4 — passing means a backend is "engine-certified" and the
mission core cannot tell them apart. This file IS the portability claim.
"""

from __future__ import annotations

import os
import time

import pytest

from backends.fake import FakeBackend
from core.geo import distance_m
from core.interfaces import DroneBackend
from core.schema import CaptureSpec, GeoPoint

RUN_PX4 = os.environ.get("RUN_PX4_CONTRACT") == "1"

BACKENDS = [
    "fake",
    pytest.param(
        "px4",
        marks=pytest.mark.skipif(
            not RUN_PX4, reason="set RUN_PX4_CONTRACT=1 with a live SITL to run"
        ),
    ),
]


async def make_backend(kind: str) -> DroneBackend:
    if kind == "fake":
        backend = FakeBackend(clock=lambda: time.time())
        await backend.connect()
        return backend
    from backends.px4_mavsdk import PX4Backend, PX4Config

    backend = PX4Backend(clock=time.time, config=PX4Config(media_dir="media_contract"))
    await backend.connect()
    return backend


async def start_point(backend: DroneBackend) -> GeoPoint:
    tel = await backend.latest_telemetry()
    assert tel is not None, "backend must produce telemetry after connect"
    return tel.position


@pytest.mark.parametrize("kind", BACKENDS)
async def test_contract_capabilities_shape(kind):
    b = await make_backend(kind)
    caps = b.capabilities()
    assert caps.name and caps.endurance_min_conservative > 0
    assert "single" in caps.supports_bracketing
    assert caps.is_physical is False  # contract runs against sims ONLY
    await b.disconnect()


@pytest.mark.parametrize("kind", BACKENDS)
async def test_contract_preflight_reports_items(kind):
    b = await make_backend(kind)
    report = await b.preflight()
    assert len(report.items) >= 3
    assert all(i.name for i in report.items)
    await b.disconnect()


@pytest.mark.parametrize("kind", BACKENDS)
async def test_contract_full_flight_cycle(kind):
    """takeoff -> goto -> capture -> RTH -> land, evidence at every stage."""
    b = await make_backend(kind)
    home = await start_point(b)

    await b.takeoff(10.0, idem=f"contract:{kind}:takeoff")
    tel = await b.latest_telemetry()
    assert tel.in_air and abs(tel.alt_rel_m - 10.0) <= 2.0

    target = GeoPoint(lat=home.lat + 0.00018, lon=home.lon)  # ~20 m north
    await b.goto(target, 10.0, 4.0, None, idem=f"contract:{kind}:goto")
    tel = await b.latest_telemetry()
    assert distance_m(tel.position, target) <= 3.0

    ref = await b.capture_photo(
        CaptureSpec(mode="single", tag="contract_shot"), idem=f"contract:{kind}:cap"
    )
    assert ref.media_id and ref.tag == "contract_shot"

    await b.return_home(idem=f"contract:{kind}:rtl")
    await b.land(idem=f"contract:{kind}:land")
    tel = await b.latest_telemetry()
    assert not tel.in_air
    assert tel.alt_rel_m <= 1.5
    await b.disconnect()


@pytest.mark.parametrize("kind", BACKENDS)
async def test_contract_idempotency_completed_commands(kind):
    """Re-sending a COMPLETED idem key must be a no-op (retry semantics)."""
    b = await make_backend(kind)
    home = await start_point(b)
    await b.takeoff(10.0, idem=f"contract:{kind}:idem-tk")

    target = GeoPoint(lat=home.lat + 0.00013, lon=home.lon)
    key = f"contract:{kind}:idem-goto"
    await b.goto(target, 10.0, 4.0, None, idem=key)
    pos_after_first = (await b.latest_telemetry()).position

    # duplicate: must not fly anywhere / must return instantly
    await b.goto(GeoPoint(lat=home.lat - 0.001, lon=home.lon), 10.0, 4.0, None, idem=key)
    pos_after_dup = (await b.latest_telemetry()).position
    assert distance_m(pos_after_first, pos_after_dup) <= 3.0

    await b.return_home(idem=f"contract:{kind}:idem-rtl")
    await b.land(idem=f"contract:{kind}:idem-land")
    await b.disconnect()


@pytest.mark.parametrize("kind", BACKENDS)
async def test_contract_telemetry_is_fresh_and_sane(kind):
    b = await make_backend(kind)
    tel = await b.latest_telemetry()
    now = time.time()
    assert -1.0 <= (now - tel.ts) <= 10.0          # fresh-ish, not from the future
    assert 0.0 <= tel.battery_pct <= 100.0
    assert -90.0 <= tel.position.lat <= 90.0
    assert 0.0 <= tel.heading_deg < 360.0
    await b.disconnect()


@pytest.mark.parametrize("kind", BACKENDS)
async def test_contract_land_when_already_landed_is_ok(kind):
    """RTL often lands the aircraft; a subsequent land() must succeed, not raise."""
    b = await make_backend(kind)
    await b.land(idem=f"contract:{kind}:land-on-ground")  # never took off
    tel = await b.latest_telemetry()
    assert not tel.in_air
    await b.disconnect()
