# D9 Handoff — Shot library v1 (M3), verify live and ship

You are the Claude agent in Mike's IDE. Read `CLAUDE.md` and `TODO.md` first.
Simulation only. Camera stays `synthetic` on this Mac (D8 live-camera is PARKED
— see TODO A7; do not revisit it here). Use plain `gz_x500` — no camera vehicle.

## Step 0 — BACKUP FIRST (Mike's explicit priority: nothing before this)

iCloud evicted parts of the repo after the disk-full event (this is why git was
crashing for outside observers and some files read as placeholders). Fix that,
then immediately get every uncommitted byte onto GitHub BEFORE any verification
work:

```bash
brctl download ~/Desktop/capstone_drone && sleep 20
find ~/Desktop/capstone_drone -name "*.icloud" | wc -l   # want: 0
cd ~/Desktop/capstone_drone
git status --porcelain    # expect the D9 files, TODO.md, and the handoff files
git add -A && git commit -m "WIP backup: D9 shot library (cloud-verified, live-run pending) + TODO D8-park decision + handoffs"
git push origin main
git log --oneline -2      # confirm the WIP commit is on top and pushed
```

Sanity: `.env`, `.venv/`, `media/`, `runs/`, and vendor repos must NOT appear in
`git status` — they are gitignored; stop and fix if any show up. Report to Mike
that the backup push succeeded before continuing. The proper D9 commit at the
end of this handoff then lands on top of this backup (two commits — honest
history, that's fine).

## What the Cowork session built (2026-08-15 — trust but verify)

- `planner/shots.py` (NEW): the shot library — `front_elevated_34`,
  `exterior_orbit`, `rear_elevated`, `lot_overhead`, composed by
  `exterior_package()` / `compile_mission()`. Bearings, standoff distances, and
  gimbal pitch are COMPUTED from property geometry ("front" = the side facing
  home/launch). The library has no safety authority — its output faces the full
  validator like any other steps.
- `core/schema.py`: `Goto` gained optional `yaw_deg` (0–359.9) so static shots
  can face the structure (orbit already had face_center). No policy rule needed
  — yaw is photographic, not safety-relevant. NOTE: this changes plan hashes
  for newly built plans (expected; approvals are per-run).
- `core/engine/executor.py`: one line — `_perform` now passes `step.yaw_deg`
  to `backend.goto()` (was hardcoded `None`; the backend protocol always
  supported it).
- `planner/prompts.py`: SYSTEM_PROMPT now teaches the shot catalog + canonical
  tags and the yaw_deg convention, so live LLM plans converge to library shapes.
- `demo/fly.py`: the scripted model now compiles its draft FROM the library
  (dogfooding) — 11 captures: front 3/4, 8 orbit, rear, overhead.
- `tests/test_shots.py` (NEW): 9 tests — geometry (bearing/offset roundtrip,
  3/4 offset, aim pitch bands), static-rule cleanliness of the package, a full
  fake-backend flight (11 media, yaw plumb verified), schema bounds for yaw_deg.
- Verified in the cloud: **158 passed, 6 skipped** (was 149); ruff clean on
  changed files; keyless demo completes with 11 photos.

All of it is on disk, UNCOMMITTED.

## Do, in order

1. `cd drone-mission && source ~/.venvs/drone-mission/bin/activate && pip install -e ".[dev]"`
2. `pytest -q` → **158 passed, 6 skipped**. `ruff check demo/ planner/shots.py tests/test_shots.py` → clean.
3. Keyless rehearsal: `python -m demo.fly --backend fake --model scripted --auto-approve`
   → exit 0, `photos: 11`, tags front_34_elevated / exterior_orbit / rear_elevated / lot_overhead.
4. Sim (plain vehicle, no camera, no extra ports):
   `docker run -d --rm --name px4sitl jonasvautherin/px4-gazebo-headless:1.17.0`
   → wait for "Ready for takeoff!" in logs.
5. **The live-LLM library flight** (synthetic camera, that's correct for this Mac):
   `python -m demo.fly "Photograph this property: the full exterior package." --backend px4 --auto-approve --operator mike`
   Success = mission `completed` AND the plan visibly uses the library shapes:
   the four canonical tags, ~11 captures, and yawed gotos for the front/rear
   shots (yaw_deg in the printed steps). If the model free-styles valid-but-
   off-catalog steps, that is a PROMPT observation, not a failure — record what
   it produced in your report; do not force it.
6. Flight will be a few minutes; expect the two static-shot gotos + orbit +
   overhead. Gimbal on plain x500 may no-op with a note — known, fine.
7. Bookkeeping: add a **D9** entry to TODO.md ([x] if step 5 completed; date,
   suite count 158, live-run result incl. whether the LLM used the catalog
   tags), and update the footer: next build item is the **minimal dashboard
   (M3)**. `rm D9_HANDOFF.md`.
8. `git add -A`; verify status shows ONLY: planner/shots.py, planner/prompts.py,
   core/schema.py, core/engine/executor.py, demo/fly.py, tests/test_shots.py,
   TODO.md, deletion of this file (plus nothing from .env/media/runs/vendor).
   Commit in house style, e.g.:
   `D9: shot library v1 (front/rear 3/4, orbit, overhead) + Goto.yaw_deg; live LLM converges to catalog (158 tests)`
   then `git push origin main`.

## Hard rules (mirror CLAUDE.md; binding)

- Never weaken core/ safety code, validators, approval, or tests.
- Expected diff surface: exactly the files listed above + TODO.md.
- 3-strikes rule: same error after 3 distinct attempts → stop and write it up.

## Report

Suite count, keyless demo result, the live plan's steps (did the LLM use the
catalog? tags? yaw?), flight outcome + photo count, files changed, surprises.
Durable facts → TODO.md.
