"""PX4Backend — the mission core's adapter to a real autopilot via MAVSDK.

Same contract as FakeBackend (core/interfaces.py), translated to PX4:
- motion   -> MAVSDK Action (arm/takeoff/goto_location/RTL/land/hold)
- gimbal   -> MAVSDK Gimbal (defensive: API drift + gimbal-less airframes tolerated)
- telemetry-> cached MAVSDK telemetry streams -> TelemetrySnapshot
- capture  -> pluggable CameraMode:
      "synthetic": writes an evidence JPEG stub + telemetry sidecar (default —
                   works on any SITL, keeps D6 runnable before camera wiring)
      "rtsp":      grabs a real frame from an RTSP stream (the headless Docker
                   image serves the sim camera at rtsp://<host>:8554/live)
- idempotency: completed idem keys are no-ops, same semantics as FakeBackend.

Waiting philosophy: backend methods return when there is telemetry EVIDENCE the
command finished (position within tolerance, on ground, at altitude) or raise
CommandTimeout — the executor's watchdog wraps everything anyway.

MAVSDK import is lazy so environments without it (pure-fake CI) still import
this module; connect() raises BackendUnavailable with instructions instead.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path

from core.geo import distance_m
from core.interfaces import (
    BackendCapabilities,
    BackendUnavailable,
    CommandRejected,
    CommandTimeout,
    MediaRef,
    PreflightItem,
    PreflightReport,
    TelemetrySnapshot,
)
from core.schema import CaptureSpec, GeoPoint

POLL_S = 0.2


@dataclass
class PX4Config:
    system_address: str = "udpin://0.0.0.0:14540"  # MAVSDK listen addr (Docker SITL default)
    camera_mode: str = "synthetic"                  # "synthetic" | "rtsp"
    rtsp_url: str = "rtsp://127.0.0.1:8554/live"
    media_dir: str = "media"
    endurance_min: float = 18.0                     # conservative for the sim battery model
    is_physical: bool = False                       # NEVER default a PX4 target to physical
    default_speed_ms: float = 5.0
    arrive_tolerance_m: float = 2.5
    alt_tolerance_m: float = 1.5
    command_wait_s: float = 120.0                   # per-motion evidence wait ceiling


class PX4Backend:
    name = "px4"

    def __init__(self, clock: Callable[[], float], config: PX4Config | None = None) -> None:
        self.clock = clock
        self.cfg = config or PX4Config()
        self._system = None            # mavsdk.System
        self._tasks: list[asyncio.Task] = []
        self._seen_idem: set[str] = set()
        self._media_seq = 0
        self._home_abs_alt: float | None = None
        self._home: GeoPoint | None = None

        # telemetry cache: field -> (value, updated_at_ts)
        self._cache: dict[str, tuple[object, float]] = {}

    # ------------------------------------------------------------------ setup

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name=self.name,
            is_physical=self.cfg.is_physical,
            supports_orbit_fastpath=False,   # we fly the portable ring; do_orbit fast-path later
            supports_bracketing=frozenset({"single", "bracket3", "bracket5"}),
            supports_gimbal_pitch=True,
            min_takeoff_alt_m=2.0,
            endurance_min_conservative=self.cfg.endurance_min,
        )

    async def connect(self) -> None:
        try:
            from mavsdk import System
        except ImportError as exc:  # pragma: no cover
            raise BackendUnavailable(
                "mavsdk is not installed — pip install mavsdk"
            ) from exc

        self._system = System()
        await self._system.connect(system_address=self.cfg.system_address)

        # wait for the autopilot to appear
        async for state in self._system.core.connection_state():
            if state.is_connected:
                break

        # spawn telemetry cachers (each stream updates one cache slot)
        t = self._system.telemetry
        self._tasks = [
            asyncio.ensure_future(self._cache_stream(t.position(), "position")),
            asyncio.ensure_future(self._cache_stream(t.heading(), "heading")),
            asyncio.ensure_future(self._cache_stream(t.battery(), "battery")),
            asyncio.ensure_future(self._cache_stream(t.gps_info(), "gps")),
            asyncio.ensure_future(self._cache_stream(t.in_air(), "in_air")),
            asyncio.ensure_future(self._cache_stream(t.armed(), "armed")),
            asyncio.ensure_future(self._cache_stream(t.flight_mode(), "flight_mode")),
            asyncio.ensure_future(self._cache_stream(t.velocity_ned(), "velocity")),
            asyncio.ensure_future(self._cache_stream(t.health(), "health")),
        ]

        # home position (for AMSL conversion + RTH evidence)
        async for home in t.home():
            self._home_abs_alt = home.absolute_altitude_m
            self._home = GeoPoint(lat=home.latitude_deg, lon=home.longitude_deg)
            break

    async def disconnect(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        if self._system is not None:
            # mavsdk spawns a bundled mavsdk_server subprocess per System() that
            # outlives the process if never told to stop (leaks a UDP bind on
            # cfg.system_address, breaking the NEXT connect()). No public API
            # for this; use the same private hook mavsdk itself calls on reconnect.
            stop = getattr(self._system, "_stop_mavsdk_server", None)
            if callable(stop):
                stop()
        self._system = None

    async def _cache_stream(self, stream, key: str) -> None:  # pragma: no cover (needs SITL)
        try:
            async for value in stream:
                self._cache[key] = (value, self.clock())
        except asyncio.CancelledError:
            return

    def _get(self, key: str):
        item = self._cache.get(key)
        return item[0] if item else None

    # ------------------------------------------------------------- telemetry

    async def latest_telemetry(self) -> TelemetrySnapshot | None:
        pos = self._get("position")
        if pos is None:
            return None
        health = self._get("health")
        gps = self._get("gps")
        battery = self._get("battery")
        vel = self._get("velocity")
        heading = self._get("heading")
        oldest_ts = min(ts for _v, ts in self._cache.values())

        speed = 0.0
        vspeed = 0.0
        if vel is not None:
            speed = (vel.north_m_s**2 + vel.east_m_s**2) ** 0.5
            vspeed = -vel.down_m_s

        return TelemetrySnapshot(
            ts=oldest_ts,
            position=GeoPoint(lat=pos.latitude_deg, lon=pos.longitude_deg),
            alt_rel_m=pos.relative_altitude_m,
            heading_deg=(heading.heading_deg % 360.0) if heading else 0.0,
            speed_ms=speed,
            vspeed_ms=vspeed,
            battery_pct=battery.remaining_percent if battery else 0.0,
            gps_ok=bool(health.is_global_position_ok) if health else False,
            sat_count=gps.num_satellites if gps else None,
            link_ok=True,  # we ARE receiving telemetry; staleness is judged by ts
            flight_mode=str(self._get("flight_mode") or "UNKNOWN"),
            armed=bool(self._get("armed")),
            in_air=bool(self._get("in_air")),
            manual_input_detected=False,  # SITL has no sticks; physical uses RC status (G5 work)
        )

    async def telemetry(self) -> AsyncIterator[TelemetrySnapshot]:  # pragma: no cover
        while True:
            snap = await self.latest_telemetry()
            if snap:
                yield snap
            await asyncio.sleep(POLL_S)

    # -------------------------------------------------------------- preflight

    async def preflight(self) -> PreflightReport:
        self._require_connected()
        health = self._get("health")
        battery = self._get("battery")
        items = [
            PreflightItem(name="telemetry", ok=bool(self._cache), detail=f"{len(self._cache)} streams"),
            PreflightItem(
                name="global_position",
                ok=bool(health.is_global_position_ok) if health else False,
            ),
            PreflightItem(
                name="home_position",
                ok=bool(health.is_home_position_ok) if health else False,
            ),
            PreflightItem(
                name="battery",
                ok=(battery.remaining_percent > 15) if battery else False,
                detail=f"{battery.remaining_percent:.0f}%" if battery else "unknown",
            ),
        ]
        return PreflightReport(items=items)

    # ----------------------------------------------------------------- motion

    async def takeoff(self, alt_m: float, *, idem: str) -> None:
        if self._dup(idem):
            return
        self._require_connected()
        a = self._system.action
        try:
            await a.set_takeoff_altitude(alt_m)
            await a.arm()
            await a.takeoff()
        except Exception as exc:
            raise CommandRejected(f"takeoff rejected: {exc}") from exc
        await self._wait(lambda t: t.in_air and abs(t.alt_rel_m - alt_m) <= self.cfg.alt_tolerance_m,
                         f"takeoff to {alt_m} m")
        self._done(idem)

    async def goto(
        self, p: GeoPoint, alt_m: float, speed_ms: float, yaw_deg: float | None, *, idem: str
    ) -> None:
        if self._dup(idem):
            return
        self._require_connected()
        if self._home_abs_alt is None:
            raise CommandRejected("no home altitude known — cannot convert relative altitude")
        a = self._system.action
        try:
            try:
                await a.set_current_speed(speed_ms)
            except Exception:
                pass  # older firmwares reject outside offboard; cruise default then applies
            await a.goto_location(
                p.lat, p.lon, self._home_abs_alt + alt_m, yaw_deg if yaw_deg is not None else float("nan")
            )
        except Exception as exc:
            raise CommandRejected(f"goto rejected: {exc}") from exc
        await self._wait(
            lambda t: distance_m(t.position, p) <= self.cfg.arrive_tolerance_m
            and abs(t.alt_rel_m - alt_m) <= self.cfg.alt_tolerance_m,
            f"goto ({p.lat:.6f},{p.lon:.6f}) @ {alt_m} m",
        )
        self._done(idem)

    async def set_gimbal_pitch(self, pitch_deg: float, *, idem: str) -> None:
        if self._dup(idem):
            return
        self._require_connected()
        g = self._system.gimbal
        try:
            # MAVSDK v3 signature (gimbal_id, ...); fall back to older v2 shapes.
            from mavsdk.gimbal import ControlMode, GimbalMode, SendMode  # type: ignore

            try:
                await g.take_control(0, ControlMode.PRIMARY)
                await g.set_angles(0, 0.0, pitch_deg, 0.0, GimbalMode.YAW_FOLLOW, SendMode.ONCE)
            except TypeError:
                await g.take_control(ControlMode.PRIMARY)          # v2
                await g.set_pitch_and_yaw(pitch_deg, 0.0)           # v2
        except Exception as exc:
            # Gimbal-less airframe or protocol quirk: record-and-continue is the
            # sim-world call; strictness for real aircraft arrives with G5 work.
            self._note_media_event("gimbal_unavailable", {"pitch_deg": pitch_deg, "error": str(exc)})
        self._done(idem)

    async def capture_photo(self, spec: CaptureSpec, *, idem: str) -> MediaRef:
        if self._dup(idem):
            return self._media_ref_for(idem, spec)
        tel = await self.latest_telemetry()
        ref = self._media_ref_for(idem, spec)
        media_path = Path(self.cfg.media_dir)
        media_path.mkdir(parents=True, exist_ok=True)
        jpg = media_path / f"{ref.media_id}_{spec.tag}.jpg"

        frame_written = False
        if self.cfg.camera_mode == "rtsp":
            frame_written = self._grab_rtsp_frame(jpg)
        if not frame_written:  # synthetic fallback: evidence stub
            jpg.write_bytes(_STUB_JPEG)

        sidecar = jpg.with_suffix(".json")
        sidecar.write_text(
            json.dumps(
                {
                    "media_id": ref.media_id,
                    "tag": spec.tag,
                    "mode": spec.mode,
                    "camera_mode": self.cfg.camera_mode if frame_written else "synthetic",
                    "ts": self.clock(),
                    "telemetry": tel.model_dump(mode="json") if tel else None,
                },
                indent=2,
            )
        )
        self._done(idem)
        return ref.model_copy(update={"path": str(jpg)})

    def _grab_rtsp_frame(self, out: Path) -> bool:
        try:  # pragma: no cover (needs stream)
            import cv2  # lazy: only needed in rtsp mode

            cap = cv2.VideoCapture(self.cfg.rtsp_url)
            try:
                if not cap.isOpened():
                    return False
                # The first reads on an H.264 RTSP stream can precede the first
                # keyframe (partial/failed decode), and a buffered frame can be
                # stale. Read a handful and keep the LAST good one: freshest
                # image, past the keyframe warm-up.
                frame = None
                for _ in range(5):
                    ok, f = cap.read()
                    if ok and f is not None:
                        frame = f
                if frame is None:
                    return False
                cv2.imwrite(str(out), frame)
                return True
            finally:
                cap.release()
        except Exception:
            return False

    async def hold(self) -> None:
        self._require_connected()
        try:
            await self._system.action.hold()
        except Exception as exc:
            raise CommandRejected(f"hold rejected: {exc}") from exc

    async def return_home(self, *, idem: str) -> None:
        if self._dup(idem):
            return
        self._require_connected()
        try:
            await self._system.action.return_to_launch()
        except Exception as exc:
            raise CommandRejected(f"RTL rejected: {exc}") from exc
        home = self._home
        await self._wait(
            lambda t: (not t.in_air)
            or (home is not None and distance_m(t.position, home) <= self.cfg.arrive_tolerance_m * 2),
            "return to launch",
        )
        self._done(idem)

    async def land(self, *, idem: str) -> None:
        if self._dup(idem):
            return
        self._require_connected()
        tel = await self.latest_telemetry()
        if tel is not None and not tel.in_air:
            self._done(idem)  # RTL already landed us — success, not an error
            return
        try:
            await self._system.action.land()
        except Exception as exc:
            raise CommandRejected(f"land rejected: {exc}") from exc
        await self._wait(lambda t: not t.in_air, "land")
        try:
            await self._system.action.disarm()
        except Exception:
            pass  # PX4 auto-disarms after landing; explicit disarm is belt-and-suspenders
        self._done(idem)

    async def abort_motion(self) -> None:
        """Stop moving NOW: PX4 Hold mode freezes the aircraft in place."""
        self._require_connected()
        try:
            await self._system.action.hold()
        except Exception:
            pass  # abort must never raise; executor proceeds to recovery regardless

    async def fetch_media(self, ref: MediaRef) -> str:
        return ref.path or ""

    # ------------------------------------------------------------------ utils

    def _require_connected(self) -> None:
        if self._system is None:
            raise BackendUnavailable(
                "PX4Backend not connected. Start SITL (e.g. "
                "`docker run --rm -it jonasvautherin/px4-gazebo-headless:1.17.0`) "
                "and call connect() first."
            )

    def _dup(self, idem: str) -> bool:
        return idem in self._seen_idem

    def _done(self, idem: str) -> None:
        self._seen_idem.add(idem)

    def _media_ref_for(self, idem: str, spec: CaptureSpec) -> MediaRef:
        import hashlib

        return MediaRef(
            media_id=hashlib.sha256(idem.encode()).hexdigest()[:12],
            tag=spec.tag,
            ts=self.clock(),
        )

    def _note_media_event(self, kind: str, payload: dict) -> None:
        p = Path(self.cfg.media_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "backend_notes.jsonl").open("a").write(
            json.dumps({"kind": kind, "ts": self.clock(), **payload}) + "\n"
        )

    async def _wait(self, done, what: str) -> None:
        deadline = self.clock() + self.cfg.command_wait_s
        while True:
            tel = await self.latest_telemetry()
            if tel is not None and done(tel):
                return
            if self.clock() > deadline:
                raise CommandTimeout(f"no evidence of completion: {what}")
            await asyncio.sleep(POLL_S)


# A minimal valid JPEG (2x2 gray) used as the synthetic-capture evidence stub.
_STUB_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080002000201011100ffc40014000100000000000000000000000000000008ffc40014100100000000000000000000000000000000ffda0008010100003f00bf8001ffd9"
)
