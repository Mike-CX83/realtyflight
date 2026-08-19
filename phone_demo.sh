#!/usr/bin/env bash
# ============================================================================
# phone_demo.sh — RealtyFlight ONE-COMMAND phone demo.
#
#   ./phone_demo.sh              full demo: real PX4 simulator + live LLM
#   ./phone_demo.sh --scripted   PX4 simulator, scripted planner (no API key)
#   ./phone_demo.sh --fake       instant fake drone (no Docker at all)
#
# It handles everything: starts Docker Desktop if needed, boots the PX4
# simulator, finds/repairs the Python env, launches the dashboard, and prints
# the URL + token for your phone. Ctrl-C stops everything SAFELY — the server
# auto-aborts and recovers any flying mission before exiting (D12.3), then
# this script removes the simulator container.
#
# Saved settings: drone-mission/.phone_demo.env (e.g. DASH_PARCEL_URL for the
# real Tulsa parcel lookups). Works on macOS bash 3.2.
# ============================================================================
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/drone-mission" 2>/dev/null || cd "$HERE" || exit 1
[ -f "server/__main__.py" ] || { echo "!! run me from the capstone_drone folder (drone-mission not found)"; exit 1; }

MODE="px4"; MODEL=""
for a in "$@"; do
  case "$a" in
    --fake)     MODE="fake"; MODEL="scripted";;
    --scripted) MODEL="scripted";;
    *) echo "unknown flag: $a (try --fake or --scripted)";;
  esac
done

# ---- Python env (find it, or build it — first run only) -------------------
if [ -f "$HOME/.venvs/drone-mission/bin/activate" ]; then
  . "$HOME/.venvs/drone-mission/bin/activate"
elif [ -f ".venv/bin/activate" ]; then
  . ".venv/bin/activate"
else
  echo ".. no Python env found — creating one (first run only, ~a minute)"
  python3 -m venv .venv && . .venv/bin/activate && pip -q install -e ".[dev]"
fi
python -c "import fastapi, uvicorn, shapely" 2>/dev/null || {
  echo ".. installing/refreshing dependencies"
  pip -q install -e ".[dev]"
}

# ---- saved demo settings (agent maintains this; parcel URL lives here) ----
[ -f ".phone_demo.env" ] && . ".phone_demo.env"

# ---- simulator -------------------------------------------------------------
if [ "$MODE" = "px4" ]; then
  if ! docker info >/dev/null 2>&1; then
    echo ".. Docker isn't running — starting Docker Desktop"
    open -a Docker 2>/dev/null
    i=0
    until docker info >/dev/null 2>&1; do
      i=$((i+1))
      [ "$i" -gt 45 ] && { echo "!! Docker never came up. Open Docker Desktop, then re-run me."; exit 1; }
      sleep 2
    done
  fi
  docker rm -f px4sitl >/dev/null 2>&1
  echo ".. starting the PX4 simulator (boot takes ~40 s; first-ever run also downloads it)"
  docker run -d -t --rm --name px4sitl jonasvautherin/px4-gazebo-headless:1.17.0 >/dev/null || {
    echo "!! simulator failed to start — is Docker healthy?"; exit 1; }
  trap 'echo; echo ".. cleaning up simulator"; docker rm -f px4sitl >/dev/null 2>&1' EXIT
fi

# ---- this machine's address on your Wi-Fi ----------------------------------
# Primary: the Mac's Bonjour name — phones resolve it, no IP hunting ever.
HOSTLOCAL="$(scutil --get LocalHostName 2>/dev/null)"
IP=""
for ifc in en0 en1 en2 en3 en4; do
  IP="$(ipconfig getifaddr "$ifc" 2>/dev/null)" && [ -n "$IP" ] && break
done
[ -z "${IP:-}" ] && IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -n "${HOSTLOCAL:-}" ]; then
  ADDR="$HOSTLOCAL.local"
elif [ -n "${IP:-}" ]; then
  ADDR="$IP"
else
  ADDR="<this-machines-IP>"
fi

SECRET="$(openssl rand -hex 6 2>/dev/null || echo "demo$$")"
PORT="${DASH_PORT:-8000}"

echo
echo "===================================================================="
echo "   RealtyFlight PHONE DEMO   (mode: $MODE${MODEL:+, planner: $MODEL})"
echo ""
echo "   On your phone (same Wi-Fi), open:   http://$ADDR:$PORT"
[ -n "${IP:-}" ] && [ "$ADDR" != "$IP" ] && echo "   (if that name doesn't load, use:     http://$IP:$PORT)"
echo "   operator name: Mike        token: $SECRET"
echo ""
echo "   1) Type an address (try: 305 S Kenosha Ave, Tulsa, OK) -> Look up"
echo "   2) Describe the shoot -> Plan mission -> read the safety checklist"
echo "   3) APPROVE and watch the map. Mid-flight, try HOLD, then KILL."
echo ""
echo "   Ctrl-C here ends the demo SAFELY (auto-abort + landing + cleanup)."
echo "===================================================================="
echo
if [ "$MODE" = "px4" ]; then
  echo ".. connecting to the simulator (the server waits for full telemetry;"
  echo "   if it exits saying streams are missing, the sim was still booting —"
  echo "   just re-run me)"
fi

DASH_BACKEND="$MODE" \
DASH_SECRET="$SECRET" \
DASH_PORT="$PORT" \
DASH_MODEL="${MODEL:-${DASH_MODEL:-}}" \
DASH_PARCEL_URL="${DASH_PARCEL_URL:-}" \
python -m server
