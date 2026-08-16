# D10 Handoff — hardening pass: re-certify and ship

You are the Claude agent in Mike's IDE. Read `CLAUDE.md` and `TODO.md` first
(the D10 entry describes everything). The Cowork session has ALREADY built and
cloud-verified the whole pass; your job is re-certification on this machine,
the SITL contract re-run (backend telemetry semantics changed), and the push.
If D9_HANDOFF.md still exists, run it FIRST in this same session (its live
flight), then this one.

## What changed (all on disk, uncommitted — trust but verify)

**Four review defects, regression-tested first (each test was proven to FAIL
on the pre-fix code), then fixed:**
1. `core/engine/executor.py` — abort recovery now requires LANDED telemetry
   evidence before `touchdown()`; a failed recovery ends in `failed` with a
   `recovery.unresolved` event instead of lying "completed" (P0).
2. `core/policy/rules_wave3.py` — GEO-03 now checks every connecting leg
   (home→target, target→target, orbit entry, return-home) as a straight
   corridor of ±acceptance width; concave boundaries can no longer be crossed
   between two legal endpoints (P0).
3. Executor `Hold` now calls `backend.hold()` and actually waits its
   `duration_s`, abort-awarely (waits on the abort event, never a blind sleep).
4. `core/schema.py` — new `orbit_capture_count()` is the single counting
   source for forecast AND execution; capture-less orbits forecast zero.

**D8-review concurrency fixes in `backends/px4_mavsdk/backend.py`:**
- RTSP grab runs in `asyncio.to_thread` (cv2 no longer blocks the event loop
  feeding telemetry); in `camera_mode="rtsp"` a failed grab raises a typed
  `CommandTimeout` — the synthetic stub is now exclusive to synthetic mode.
- Snapshot `ts` reflects flight-critical streams (position/velocity/in_air/
  armed); stale auxiliary streams degrade their OWN field: health older than
  10 s ⇒ `gps_ok=False`, battery older than 10 s ⇒ 0% (PWR-01 then refuses).
- A cacher stream that dies removes its cache slot and records into
  `_stream_errors` — dead data can never linger as live truth.

**Repo health:** repo-wide ruff 53 → 0 (`ruff check .` is clean); root
`README.md` (new — real-vs-sim, safety boundary, quickstart, demo);
`.github/workflows/ci.yml` (ruff + pytest on every push); `requirements.lock`
(reference lock from the verification env); `drone-mission/README.md`
refreshed (was stale at 146 tests). New test file: `tests/test_hardening_d10.py`
(22 tests). Suite: **180 passed, 6 skipped** in the cloud.

## Do, in order

1. `cd drone-mission && source ~/.venvs/drone-mission/bin/activate && pip install -e ".[dev]"`
2. `pytest -q` → **180 passed, 6 skipped**. `ruff check .` → clean.
3. Keyless demo: `python -m demo.fly --backend fake --model scripted --auto-approve` → exit 0.
4. **SITL re-certification (required — telemetry code changed):**
   ```bash
   docker rm -f px4sitl 2>/dev/null
   docker run -d --rm --name px4sitl jonasvautherin/px4-gazebo-headless:1.17.0
   # wait for "Ready for takeoff!" in: docker logs -f px4sitl
   RUN_PX4_CONTRACT=1 pytest tests/test_backend_contract.py -q   # expect 12 passed
   python -m backends.px4_mavsdk.smoke                            # SMOKE FLIGHT COMPLETE
   ```
5. One-time identity fix (review item): set a consistent commit identity —
   `git config user.email "<Mike's GitHub noreply email>" && git config user.name "Mike Hankins"`
   (find the noreply address at github.com → Settings → Emails).
6. Bookkeeping: tick **D10 → [x]** in TODO.md with the re-cert results (and
   D9 → [x] if you ran its handoff in this session). `rm D10_HANDOFF.md` (and
   any other completed handoff files).
7. `git add -A`; `git status` must show ONLY code/tests/docs/workflows/TODO —
   never `.env`, `.venv/`, `media/`, `runs/`, vendor repos. Commit in house
   style, e.g.:
   `D10 hardening: 4 review defects regression-tested+fixed (P0 touchdown evidence, P0 GEO-03 path corridors), RTSP off-loop + typed failure, per-stream telemetry freshness, ruff 53->0, root README + CI + lock (180 tests)`
   Push. Then check the repo's Actions tab: the FIRST CI run should go green —
   if it fails, fix the workflow (not the tests) and report why.

## Known + accepted (do not chase tonight)

- mypy reports ~41 advisory findings (Optional-narrowing, stubs) — documented,
  not CI-gated; a later pass can burn them down.
- python-statemachine deprecation warnings (`current_state`) — library-wide
  rename, harmless; migrate in a quiet moment, not now.
- The feature freeze LIFTS once this push lands and CI is green — next build
  item is the M3 dashboard.

## Hard rules (mirror CLAUDE.md; binding)

- If any test fails on this machine that passed in the cloud (180/6), STOP
  and report the exact diff in environment/output — do not "fix" tests.
- 3-strikes rule on any repeated error: stop and write it up.

## Report

Suite + contract + smoke results, CI run link/status, files committed, and
anything surprising. Durable facts → TODO.md.
