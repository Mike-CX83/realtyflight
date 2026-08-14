"""The backend-neutral contract: what ANY drone (fake, PX4-sim, Parrot) must
look like to the mission core.

Design note (doc 08 §6, refined): these types live in `core/` — not in
`backends/` — so the dependency arrow only ever points one way:
backends import core; core never imports a backend. The core cannot tell
PX4 from Parrot from a test fake, which is the whole portability claim.

No SDK imports allowed in this file, ever.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable
from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict, Field

from core.schema import CaptureSpec, GeoPoint

# --------------------------------------------------------------------------- #
# Data the drone reports
# --------------------------------------------------------------------------- #


class TelemetrySnapshot(BaseModel):
    """One moment of drone truth. `ts` is a Unix timestamp set by the backend
    when the data was CURRENT — freshness checks compare it to the caller's
    clock (injected, never read inside rules)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ts: float
    position: GeoPoint
    alt_rel_m: float
    heading_deg: float = Field(ge=0.0, lt=360.0)
    speed_ms: float = Field(ge=0.0)
    vspeed_ms: float
    battery_pct: float = Field(ge=0.0, le=100.0)
    gps_ok: bool
    sat_count: int | None = Field(default=None, ge=0)
    link_ok: bool
    flight_mode: str
    armed: bool
    in_air: bool
    manual_input_detected: bool = False


class BackendCapabilities(BaseModel):
    """What this particular aircraft/simulator can actually do. CAP-01 denies
    any plan step the selected backend does not support — no silent downgrades."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    is_physical: bool = False                      # True ONLY for a real aircraft (ENV-01)
    supports_orbit_fastpath: bool = False          # PX4 do_orbit; ring fallback otherwise
    supports_bracketing: frozenset[str] = frozenset({"single"})
    supports_gimbal_pitch: bool = False
    positioning: Literal["gps"] = "gps"            # future: "vio"
    min_takeoff_alt_m: float = Field(default=2.0, gt=0.0)
    endurance_min_conservative: float = Field(gt=0.0)  # deliberately pessimistic minutes


class MediaRef(BaseModel):
    """Evidence that a capture happened; the executor links it to its step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    media_id: str
    tag: str
    ts: float
    step_index: int | None = None
    path: str | None = None  # local file once fetched


class PreflightItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    ok: bool
    detail: str = ""


class PreflightReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    items: list[PreflightItem]

    @property
    def ok(self) -> bool:
        return all(i.ok for i in self.items)


# --------------------------------------------------------------------------- #
# Error taxonomy — adapters translate SDK errors into exactly these;
# the executor's fault logic switches on these, never on SDK exceptions.
# --------------------------------------------------------------------------- #


class BackendError(Exception):
    """Base for everything a backend may raise."""


class BackendUnavailable(BackendError):
    """Cannot connect / connection lost before a command was accepted."""


class CommandRejected(BackendError):
    """The vehicle refused the command (mode, interlock, invalid state)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class CommandTimeout(BackendError):
    """No completion evidence within the watchdog window. Retryable (bounded)."""


class LinkLost(BackendError):
    """Telemetry/command link died mid-operation."""


class SafetyInterlock(BackendError):
    """The backend's own safety layer blocked us (e.g., obstacle-avoidance freeze)."""

    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.source = source


# --------------------------------------------------------------------------- #
# The DroneBackend protocol (implemented by backends/fake, /px4_mavsdk, /parrot_olympe)
# --------------------------------------------------------------------------- #


@runtime_checkable
class DroneBackend(Protocol):
    """Every method that moves the aircraft takes an idempotency key (`idem`):
    resending the same key must not repeat the action (doc 01 S9)."""

    name: str

    def capabilities(self) -> BackendCapabilities: ...

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...

    async def preflight(self) -> PreflightReport: ...

    async def takeoff(self, alt_m: float, *, idem: str) -> None: ...
    async def goto(
        self, p: GeoPoint, alt_m: float, speed_ms: float, yaw_deg: float | None, *, idem: str
    ) -> None: ...
    async def set_gimbal_pitch(self, pitch_deg: float, *, idem: str) -> None: ...
    async def capture_photo(self, spec: CaptureSpec, *, idem: str) -> MediaRef: ...
    async def hold(self) -> None: ...
    async def return_home(self, *, idem: str) -> None: ...
    async def land(self, *, idem: str) -> None: ...
    async def abort_motion(self) -> None: ...

    def telemetry(self) -> AsyncIterator[TelemetrySnapshot]: ...
    async def latest_telemetry(self) -> TelemetrySnapshot | None: ...

    async def fetch_media(self, ref: MediaRef) -> str: ...
