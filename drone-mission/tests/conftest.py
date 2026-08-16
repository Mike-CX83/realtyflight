"""Shared fixtures: a known-good mission and helpers to mutate it."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root on path

from core.schema import MissionPlan  # noqa: E402


def good_plan_dict() -> dict[str, Any]:
    """The representative first mission (doc 00 §8): takeoff, orbit with 8
    captures, overhead lot shot, home, land — on a simple square property."""
    center = {"lat": 36.1540, "lon": -95.9928}  # Tulsa-ish, arbitrary
    boundary = [
        {"lat": 36.15450, "lon": -95.99330},
        {"lat": 36.15450, "lon": -95.99230},
        {"lat": 36.15350, "lon": -95.99230},
        {"lat": 36.15350, "lon": -95.99330},
    ]
    return {
        "plan_version": 1,
        "mission_id": "01TESTMISSION0000000000000",
        "request_text": "Photograph this property: orbit the house and give me "
        "an exterior package.",
        "summary": "Take off to 25 m, orbit the house at 20 m radius capturing 8 bracketed photos, "
        "climb for 1 overhead lot shot, return home and land.",
        "property": {
            "center": center, "boundary": boundary,
            "home": {"lat": 36.15360, "lon": -95.99320},
        },
        "limits": {},
        "failsafe": {},
        "steps": [
            {"action": "takeoff", "alt_m": 25.0},
            {"action": "goto", "to": {"lat": 36.15420, "lon": -95.99300},
             "alt_m": 25.0, "speed_ms": 4.0},
            {"action": "set_gimbal", "pitch_deg": -20.0},
            {
                "action": "orbit",
                "center": center,
                "radius_m": 20.0,
                "alt_m": 25.0,
                "speed_ms": 3.0,
                "arc_deg": 360.0,
                "captures_every_deg": 45.0,
                "capture": {"mode": "bracket3", "tag": "exterior_orbit"},
            },
            {"action": "goto", "to": center, "alt_m": 38.0, "speed_ms": 3.0},
            {"action": "set_gimbal", "pitch_deg": -90.0},
            {"action": "capture_photo", "capture": {"mode": "single", "tag": "lot_overhead"}},
            {"action": "return_home"},
            {"action": "land"},
        ],
    }


@pytest.fixture()
def good_plan() -> MissionPlan:
    return MissionPlan.model_validate(good_plan_dict())


@pytest.fixture()
def good_dict() -> dict[str, Any]:
    return good_plan_dict()


# ---- Wave 4: live-state fixtures ------------------------------------------- #

NOW = 1_766_000_000.0  # fixed fake "now" — rules never read the wall clock


def good_telemetry_dict(**overrides) -> dict[str, Any]:
    base = {
        "ts": NOW - 0.5,  # half a second old = fresh
        "position": {"lat": 36.15360, "lon": -95.99320},  # sitting at home
        "alt_rel_m": 0.0,
        "heading_deg": 90.0,
        "speed_ms": 0.0,
        "vspeed_ms": 0.0,
        "battery_pct": 95.0,
        "gps_ok": True,
        "sat_count": 14,
        "link_ok": True,
        "flight_mode": "READY",
        "armed": False,
        "in_air": False,
        "manual_input_detected": False,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def good_ctx():
    from core.interfaces import BackendCapabilities, TelemetrySnapshot
    from core.policy import ValidationContext

    return ValidationContext(
        now_ts=NOW,
        telemetry=TelemetrySnapshot.model_validate(good_telemetry_dict()),
        capabilities=BackendCapabilities(
            name="fake",
            supports_orbit_fastpath=False,
            supports_bracketing=frozenset({"single", "bracket3", "bracket5"}),
            supports_gimbal_pitch=True,
            min_takeoff_alt_m=2.0,
            endurance_min_conservative=20.0,
        ),
    )
