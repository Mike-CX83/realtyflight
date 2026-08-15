# D8 Handoff — Real Gazebo camera frames (RTSP), verified end to end

You are the Claude agent in Mike's IDE. Read `CLAUDE.md` and `TODO.md` first.
Simulation only, as always.

## What D8 is

Until now every "photo" was a 161-byte synthetic stub JPEG (honest evidence, not
an image). D8 flips `PX4Backend` to its already-plumbed RTSP mode so captures
are REAL frames from the Gazebo camera. Shot library and the dashboard remain
future work — this slice is just: the photos become actual photographs.

## What the Cowork session already did (2026-08-15 — trust but verify)

- Hardened `backends/px4_mavsdk/backend.py::_grab_rtsp_frame`: open-check,
  reads several frames past the H.264 keyframe warm-up and keeps the last good
  one, always releases the capture. Verified in the cloud against a REAL RTSP
  H.264 stream (mediamtx + ffmpeg): 3/3 captures through the full
  `capture_photo` path produced ~47 KB decoded frames with sidecars honestly
  recording `"camera_mode": "rtsp"` — and the stub fallback still engages (and
  records "synthetic") when no stream exists.
- `demo/fly.py`: new `--camera {synthetic,rtsp}` and `--rtsp-url` flags
  (defaults unchanged), camera shown in the status line, connect-failure hint
  now prints the camera-vehicle docker command.
- Regression state: `pytest -q` 148 passed / 6 skipped; `ruff check demo/`
  clean; keyless fake demo still exits 0. (`ruff` on `backends/` shows 8
  PRE-EXISTING nits — long lines, an unused `field` import, one ASYNC240 —
  untouched deliberately; clean them in this commit if you like, they are
  cosmetic.)
- Facts verified from the image docs: the camera lives on the
  `gz_x500_mono_cam` vehicle; the container serves RTSP on port 8554 at
  `/live`; the port must be published with `-p 8554:8554`.
- These changes are on disk, UNCOMMITTED: `backends/px4_mavsdk/backend.py`,
  `demo/fly.py` (and possibly `tests/test_executor.py` regression tests if you
  have not committed them yet — check `git status`).

## Do, in order

1. Environment (same venv as D7):

   ```bash
   cd drone-mission && source ~/.venvs/drone-mission/bin/activate
   pip install -e ".[dev,camera]"    # camera extra = opencv-python
   ```

2. Regression first: `pytest -q` → **148 passed, 6 skipped**; keyless demo
   `python -m demo.fly --backend fake --model scripted --auto-approve` → exit 0.

3. Start the CAMERA simulator (note the new flags — port + vehicle):

   ```bash
   docker rm -f px4sitl 2>/dev/null
   docker run -d --rm --name px4sitl -p 8554:8554 jonasvautherin/px4-gazebo-headless:1.17.0 -v gz_x500_mono_cam
   docker logs -f px4sitl   # wait for "Ready for takeoff!", then Ctrl+C the logs
   ```

4. Pre-flight camera sanity (10 s, no flight):

   ```bash
   python -c "
   import time
   from pathlib import Path
   from backends.px4_mavsdk import PX4Backend, PX4Config
   b = PX4Backend(clock=time.time, config=PX4Config(camera_mode='rtsp'))
   ok = b._grab_rtsp_frame(Path('/tmp/rtsp_probe.jpg'))
   print('grab:', ok, Path('/tmp/rtsp_probe.jpg').stat().st_size if ok else 0, 'bytes')"
   ```

   Expect `grab: True` and tens of KB. If False: `docker port px4sitl` must
   show 8554; the vehicle must be `gz_x500_mono_cam`; give the sim ~20 s after
   boot for the stream to appear.

5. **The D8 flight** — real LLM plan, real physics, real photos:

   ```bash
   python -m demo.fly "Photograph this property: orbit the house, full exterior package." --backend px4 --camera rtsp --auto-approve --operator mike
   ```

   Captures now cost ~1–3 s each (fresh RTSP connect per photo), so the flight
   runs a bit longer than D7's — that is expected, not a hang (the telemetry
   ticker keeps printing).

6. VERIFY THE PHOTOS ARE REAL — do not call D8 done on stubs:
   - every new JPEG in `media/` from this mission is **> 5 KB** (stubs are 161 B),
   - every matching `.json` sidecar says `"camera_mode": "rtsp"`,
   - open one JPEG: it should show the Gazebo world from altitude.
   If any sidecar says "synthetic", the grab fell back — fix the stream (step 4)
   and re-run; the mission "passing" is not enough.

7. Bookkeeping + git:
   - `TODO.md`: under D8 record the result (date, photos real, sizes, flight
     time) and note the remaining D8 tail: shot library v1 + minimal dashboard.
   - Known, accepted gap to note: `gz_x500_mono_cam` is a FIXED camera — no
     gimbal in this sim, so `set_gimbal` stays a recorded no-op and the
     "overhead" shot is not truly straight-down imagery. Real gimbal control
     arrives with the Sphinx/ANAFI track (M5). Do NOT try to fake it.
   - `rm D8_HANDOFF.md`, `git add -A`, verify `git status` shows ONLY:
     `backends/px4_mavsdk/backend.py`, `demo/fly.py`, `TODO.md`, the deletion,
     and (if previously uncommitted) `tests/test_executor.py` — never `.env`,
     `media/`, `runs/`, vendor repos. Commit in the house style, e.g.:
     `D8: real Gazebo camera frames over RTSP (verified vs live stream); demo --camera flag`
     and `git push origin main`.

## Hard rules (mirror CLAUDE.md; binding)

- Never weaken `core/` safety code, validators, approval, or tests.
- Expected diff surface: `backends/px4_mavsdk/backend.py`, `demo/fly.py`,
  `TODO.md`, tests. Explain anything beyond that.
- 3-strikes rule: one error surviving 3 distinct fix attempts → stop, write up
  exactly what you tried and observed.

## Finish with a report

Suite counts, the sanity-grab result, flight outcome + timeline, photo count
with real sizes, one sidecar excerpt showing `camera_mode: rtsp`, files changed
and why, anything surprising. Durable facts go in `TODO.md`.
