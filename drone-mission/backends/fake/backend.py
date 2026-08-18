"""FakeBackend — the deterministic practice drone (doc 08 §6, doc 05 §1).

Purpose-built for tests and the demo's dry-run mode:
- Kinematics are instant by default (time_scale=0) or scaled for timing tests.
- Every fault the safety core must handle is scriptable: battery level, GPS,
  link, stale telemetry, manual stick input, per-command exceptions/hangs.
- Idempotency is real: a repeated `idem` key is a no-op, so retry semantics
  are actually exercised, not pretended.
- Telemetry timestamps come from the injected clock — the same clock the
  executor and rules use, so freshness math is deterministic end-to-end.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from core.geo import distance_m
from core.interfaces import (
    BackendCapabilities,
    CommandRejected,
    MediaRef,
    PreflightItem,
    PreflightReport,
    TelemetrySnapshot,
)
from core.schema import CaptureSpec, GeoPoint


@dataclass
class FakeConfig:
    home: GeoPoint = field(default_factory=lambda: GeoPoint(lat=36.15360, lon=-95.99320))
    battery_pct: float = 95.0
    battery_drain_per_cmd_pct: float = 0.4
    time_scale: float = 0.0          # 0 => motion completes instantly
    endurance_min: float = 20.0
    is_physical: bool = False
    name: str = "fake"


class FakeBackend:
    """Implements the DroneBackend protocol. All state is inspectable by tests."""

    def __init__(self, clock: Callable[[], float], config: FakeConfig | None = None) -> None:
        self.cfg = config or FakeConfig()
        self.clock = clock
        self.name = self.cfg.name

        # -- live state (tests may poke all of this) -------------------------- #
        self.position: GeoPoint = self.cfg.home
        self.alt_rel_m: float = 0.0
        self.heading_deg: float = 0.0
        self.vspeed_ms: float = 0.0
        self.speed_ms: float = 0.0
        self.battery_pct: float = self.cfg.battery_pct
        self.gps_ok: bool = True
        self.sat_count: int = 14
        self.link_ok: bool = True
        self.armed: bool = False
        self.in_air: bool = False
        self.manual_input: bool = False
        self.telemetry_lag_s: float = 0.0   # raise to simulate stale data
        self.connected: bool = False

        # -- fault scripting --------------------------------------------------- #
        # hooks: (action, occurrence#) -> exception instance OR "hang"
        self.hooks: dict[tuple[str, int], object] = {}
        self._call_counts: dict[str, int] = {}

        # -- bookkeeping -------------------------------------------------------- #
        self.command_log: list[tuple[str, str]] = []   # (action, idem)
        self._seen_idem: set[str] = set()
        self.abort_motion_calls: int = 0
        self._media_seq = 0

    # ------------------------------------------------------------------ util

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name=self.name,
            is_physical=self.cfg.is_physical,
            supports_orbit_fastpath=False,
            supports_bracketing=frozenset({"single", "bracket3", "bracket5"}),
            supports_gimbal_pitch=True,
            min_takeoff_alt_m=2.0,
            endurance_min_conservative=self.cfg.endurance_min,
        )

    async def _maybe_fault(self, action: str) -> None:
        n = self._call_counts.get(action, 0)
        self._call_counts[action] = n + 1
        effect = self.hooks.get((action, n))
        if effect is None:
            return
        if effect == "hang":
            await asyncio.sleep(3600)  # the watchdog or abort() must save us
        if isinstance(effect, Exception):
            raise effect

    def _drain(self) -> None:
        self.battery_pct = max(0.0, self.battery_pct - self.cfg.battery_drain_per_cmd_pct)

    async def _travel(self, dist_m: float, speed_ms: float) -> None:
        if self.cfg.time_scale > 0 and speed_ms > 0:
            await asyncio.sleep((dist_m / speed_ms) * self.cfg.time_scale)

    def _is_dup(self, action: str, idem: str) -> bool:
        """True => this idem key already COMPLETED successfully. Failed attempts
        do NOT register — retries with the same key must actually re-execute
        (idempotency dedupes results, not attempts)."""
        self.command_log.append((action, idem))
        return idem in self._seen_idem

    def _done(self, idem: str) -> None:
        self._seen_idem.add(idem)

    # ------------------------------------------------------- protocol methods

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def preflight(self) -> PreflightReport:
        return PreflightReport(
            items=[
                PreflightItem(name="link", ok=self.link_ok),
                PreflightItem(name="gps", ok=self.gps_ok, detail=f"{self.sat_count} sats"),
                PreflightItem(name="battery", ok=self.battery_pct > 15,
                              detail=f"{self.battery_pct:.0f}%"),
            ]
        )

    async def takeoff(self, alt_m: float, *, idem: str) -> None:
        if self._is_dup("takeoff", idem):
            return
        await self._maybe_fault("takeoff")
        if self.in_air:
            raise CommandRejected("already in air")
        await self._travel(alt_m, 1.5)
        self.armed = True
        self.in_air = True
        self.alt_rel_m = alt_m
        self._drain()
        self._done(idem)

    async def goto(self, p: GeoPoint, alt_m: float, speed_ms: float,
                   yaw_deg: float | None, *, idem: str) -> None:
        if self._is_dup("goto", idem):
            return
        await self._maybe_fault("goto")
        if not self.in_air:
            raise CommandRejected("not in air")
        await self._travel(distance_m(self.position, p), speed_ms)
        self.position = p
        self.alt_rel_m = alt_m
        if yaw_deg is not None:
            self.heading_deg = yaw_deg % 360.0
        self._drain()
        self._done(idem)

    async def set_gimbal_pitch(self, pitch_deg: float, *, idem: str) -> None:
        if self._is_dup("set_gimbal", idem):
            return
        await self._maybe_fault("set_gimbal")
        self.gimbal_pitch_deg = pitch_deg
        self._drain()
        self._done(idem)

    async def capture_photo(self, spec: CaptureSpec, *, idem: str) -> MediaRef:
        if self._is_dup("capture_photo", idem):
            # duplicate of a COMPLETED capture: same ref, no new photo
            media_id = hashlib.sha256(idem.encode()).hexdigest()[:12]
            return MediaRef(media_id=media_id, tag=spec.tag, ts=self.clock())
        await self._maybe_fault("capture_photo")
        self._media_seq += 1
        media_id = hashlib.sha256(idem.encode()).hexdigest()[:12]
        self._drain()
        self._done(idem)
        return MediaRef(media_id=media_id, tag=spec.tag, ts=self.clock())

    async def hold(self) -> None:
        self.command_log.append(("hold", "-"))
        self.speed_ms = 0.0

    async def return_home(self, *, idem: str) -> None:
        if self._is_dup("return_home", idem):
            return
        await self._maybe_fault("return_home")
        await self._travel(distance_m(self.position, self.cfg.home), 5.0)
        self.position = self.cfg.home
        self._drain()
        self._done(idem)

    async def land(self, *, idem: str) -> None:
        if self._is_dup("land", idem):
            return
        await self._maybe_fault("land")
        await self._travel(self.alt_rel_m, 1.0)
        self.alt_rel_m = 0.0
        self.vspeed_ms = 0.0
        self.in_air = False
        self.armed = False
        self._drain()
        self._done(idem)

    async def abort_motion(self) -> None:
        self.abort_motion_calls += 1
        self.speed_ms = 0.0

    async def latest_telemetry(self) -> TelemetrySnapshot:
        return TelemetrySnapshot(
            ts=self.clock() - self.telemetry_lag_s,
            position=self.position,
            alt_rel_m=self.alt_rel_m,
            heading_deg=self.heading_deg,
            speed_ms=self.speed_ms,
            vspeed_ms=self.vspeed_ms,
            battery_pct=self.battery_pct,
            gps_ok=self.gps_ok,
            sat_count=self.sat_count if self.gps_ok else 0,
            link_ok=self.link_ok,
            flight_mode="FAKE",
            armed=self.armed,
            in_air=self.in_air,
            manual_input_detected=self.manual_input,
        )

    async def telemetry(self) -> AsyncIterator[TelemetrySnapshot]:  # pragma: no cover
        while True:
            yield await self.latest_telemetry()
            await asyncio.sleep(0.05)

    async def fetch_media(self, ref: MediaRef) -> str:
        return f"/fake/media/{ref.media_id}.jpg"
