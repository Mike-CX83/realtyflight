"""Run the dashboard:  python -m server

Env (all optional):
  DASH_BACKEND  fake | px4          (default fake)
  DASH_MODEL    PydanticAI model id, or "scripted"  (default: auto from API keys)
  DASH_SECRET   bearer token for the UI  (default: generated + printed)
  DASH_PORT     default 8000
  DASH_HOST     default 0.0.0.0 (LAN — so your phone can reach it)

The token is REQUIRED by every flight-affecting route — the printed line below
is what you paste into the dashboard's token field on your phone.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import time

import uvicorn

from demo.fly import _load_dotenv, first_telemetry, make_backend
from server.app import create_app


async def _build():
    _load_dotenv()
    kind = os.environ.get("DASH_BACKEND", "fake")
    backend = await make_backend(kind, time_scale=0.05, connect_timeout_s=60.0)
    await first_telemetry(backend)
    return backend


async def _run() -> None:
    # backend.connect() schedules its telemetry-cache tasks (asyncio.ensure_future)
    # onto whichever loop is running right now — it must be the SAME loop uvicorn
    # serves on, or those tasks are silently orphaned the moment this coroutine
    # returns and never advance again (telemetry freezes at its first snapshot).
    # (D11 regression, reintroduced by the D13 diff and fixed again here.)
    backend = await _build()
    secret = os.environ.get("DASH_SECRET") or secrets.token_urlsafe(18)
    model = os.environ.get("DASH_MODEL") or None
    app = create_app(
        backend=backend, model=model, secret=secret,
        # D13: set to your county's parcel FeatureServer layer URL to turn
        # address lookups into REAL parcel boundaries (geocode-only otherwise).
        parcel_service_url=os.environ.get("DASH_PARCEL_URL") or None,
    )

    host = os.environ.get("DASH_HOST", "0.0.0.0")
    port = int(os.environ.get("DASH_PORT", "8000"))
    print("=" * 62)
    print(f"  RealtyFlight dashboard  ->  http://<this-machine's-LAN-IP>:{port}")
    print(f"  backend: {os.environ.get('DASH_BACKEND', 'fake')}   "
          f"started {time.strftime('%H:%M:%S')}")
    print(f"  TOKEN (paste into the dashboard):  {secret}")
    print("=" * 62)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    await uvicorn.Server(config).serve()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
