# QGC Demo Handoff — make the software watchable (zero new code)

You are the Claude agent in Mike's IDE. Goal: set up QGroundControl so Mike can
run his terminal demo and SHOW someone the drone flying his mission on a live
map. This is install + run + document only — the D10 feature freeze applies,
so change NO code. Simulation only, plain `gz_x500` (no camera vehicle).

## Why this works with zero code

The SITL container already sends MAVLink to the host on UDP 14550 — the port
QGroundControl listens on by default. QGC will discover the simulated drone by
itself; while `demo.fly` commands it, QGC just watches the same aircraft.

## Do, in order

1. **Install QGroundControl:**
   - If Homebrew exists (`which brew`): `brew install --cask qgroundcontrol`
   - Otherwise download the stable macOS build from qgroundcontrol.com/downloads
     and drag to Applications. First launch may need right-click → Open
     (Gatekeeper).

2. **Start the sim** (plain vehicle — leave CPU headroom):
   ```bash
   docker rm -f px4sitl 2>/dev/null
   docker run -d --rm --name px4sitl jonasvautherin/px4-gazebo-headless:1.17.0
   docker logs -f px4sitl   # wait for "Ready for takeoff!", then Ctrl+C the logs
   ```

3. **Open QGroundControl.** Within ~15 s it should announce a vehicle and show
   it on the map (Zurich — the sim's default home). Expect "Ready To Fly".
   If no vehicle appears: check Application Settings → Comm Links (default
   UDP 14550 autoconnect should be ON), and confirm the container is running.

4. **Dry-run the show** (keyless, deterministic):
   ```bash
   cd drone-mission && source ~/.venvs/drone-mission/bin/activate
   python -m demo.fly --backend px4 --model scripted --auto-approve --operator mike
   ```
   While it flies, verify the drone MOVES on the QGC map: takeoff, the
   front-3/4 hop, the 360° orbit ring drawing itself, the rear shot, the climb
   to the overhead, return, land. To verify visually yourself, grab screenshots
   mid-flight and inspect them:
   ```bash
   screencapture -x /tmp/qgc_flight.png
   ```
   (Take 2–3 during the orbit; confirm the vehicle icon has moved between them
   and the trajectory trail is visible.)

5. **Write the show script for Mike** as `docs/DEMO.md` (this IS allowed under
   the freeze — documentation, not features). Contents: the exact two-terminal
   + QGC setup from steps 2–3, then the SHOWTIME run — live LLM and the
   interactive approval, which is the theatrical beat:
   ```bash
   python -m demo.fly "Photograph this property: the full exterior package." --backend px4
   ```
   Script beats to note in DEMO.md:
   - read the LLM's plan + validation checklist aloud off the terminal,
   - type APPROVE on camera — "a human authorizes every flight",
   - point at QGC as the orbit draws itself — "my software is flying this",
   - optional flex: Ctrl+C mid-orbit — "and this is the abort: watch it come
     home on its own" (run this once in rehearsal so Mike trusts it),
   - finish on the audit trail printout + `media/` gallery — "every decision
     is logged; the log alone can replay the mission",
   - QuickTime screen-record (Cmd+Shift+5) a full run and save it as
     `docs/demo_recording_<date>.mov` NOTE: do not git-add the .mov if it's
     large — note its filename in DEMO.md instead.

6. **Bookkeeping:** add one line to TODO.md under the footer's build queue:
   demo-readiness achieved via QGC (see docs/DEMO.md). Commit `docs/DEMO.md` +
   the TODO line (+ the still-uncommitted TODO edits already on disk) in house
   style, push, and `rm QGC_DEMO_HANDOFF.md`.

## Hard rules

- NO code changes (D10 freeze). Install, run, screenshot, document only.
- If QGC can't see the vehicle after 3 distinct fixes: stop, write up exactly
  what you observed (container logs + QGC comm-link settings), report.

## Report

QGC install method + version, whether the vehicle auto-appeared, screenshot
evidence the aircraft moved during the scripted flight, where DEMO.md lives,
and anything Mike should know before doing it live in front of a person.
