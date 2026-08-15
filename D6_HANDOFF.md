# D6 Handoff — First live PX4 SITL flight + contract suite

You are the Claude agent working in Mike's IDE on his Mac. This file is your task
briefing, written by a Cowork session earlier today. Read `CLAUDE.md` and `TODO.md`
at the repo root before doing anything — `CLAUDE.md` is binding.

We are at TODO item **D6**: `backends/px4_mavsdk/` (the PX4 adapter) is written and
unit-tested, but has never flown against a live PX4 SITL. Your job is to run that
first live flight and the contract suite, on this Mac, **in simulation only**.

## State as of earlier today (trust but verify)

- Docker Desktop is installed and working on this Apple Silicon Mac
  (`docker run --rm hello-world` passed, arm64v8).
- The image `jonasvautherin/px4-gazebo-headless:1.17.0` is already pulled and booted
  cleanly once: Gazebo world + x500 spawned, `Startup script returned successfully`,
  home set. A container may or may not still be running — check with `docker ps`.
- Its boot log said `MAVLink only on localhost`, so on macOS the sim's telemetry
  likely won't reach the host unless the container is started with the Mac's IP
  (fallback in step 3 below).
- `drone-mission/.venv` exists; the project installs with `pip install -e ".[dev]"`.

## Do, in order

1. Ensure the sim is running. If not:

   ```bash
   docker run -d --rm --name px4sitl jonasvautherin/px4-gazebo-headless:1.17.0
   ```

   and follow `docker logs -f px4sitl` until `Ready for takeoff!`.

2. Set up the environment:

   ```bash
   cd drone-mission && source .venv/bin/activate && pip install -e ".[dev]"
   ```

3. Run the smoke flight:

   ```bash
   python -m backends.px4_mavsdk.smoke
   ```

   Expected: connect → preflight ok → takeoff 10 m → ~30 m leg with arrival evidence
   → synthetic photo → RTL → land → `SMOKE FLIGHT COMPLETE — the adapter speaks PX4.`

   If it hangs at `connecting to SITL (udp :14540)` for ~90 s, that's the localhost
   issue. Fix:

   ```bash
   docker rm -f px4sitl
   docker run -d --rm --name px4sitl jonasvautherin/px4-gazebo-headless:1.17.0 -v gz_x500 $(ipconfig getifaddr en0)
   ```

   Wait for ready in `docker logs -f px4sitl`, then rerun the smoke test.

4. After smoke passes, run the portability proof — the same 6 tests that pass on the
   fake backend must pass on PX4:

   ```bash
   RUN_PX4_CONTRACT=1 pytest tests/test_backend_contract.py -q
   ```

5. Run plain `pytest -q` once more to confirm the full non-SITL suite (~146 tests)
   is still green.

6. On success, update `TODO.md`: mark D6 `[x]` with today's date and a one-line
   result (smoke outcome + contract/full test counts + any fix made). Then clean up:
   `docker rm -f px4sitl`.

## Hard rules (these mirror CLAUDE.md and are binding)

- **Simulation only.** Never weaken, skip, or mock `core/` safety code, validators,
  or the contract suite to get green. If a contract test fails, the suspect is
  `backends/px4_mavsdk/backend.py` — fix the adapter and explain the bug.
- Keep diffs small and inside `backends/px4_mavsdk/` or `tests/` unless a
  cross-cutting bug is proven. Do not touch `research/` vendor repos. No wholesale
  dependency upgrades.
- If the same error survives 3 distinct fix attempts, **stop** and write up exactly
  what you tried and observed instead of improvising architecture changes.

## Step 7 — Git (do this last, only after D6 is green)

The repo already has 2 commits and a GitHub remote (`origin/main`, fully pushed), so
while updating `TODO.md` also mark **D1** `[x]` — it's done, just never got ticked.
Then:

1. Clean the iCloud junk that leaked into git internals (causes the
   `ignoring ref with broken name refs/Icon?` warnings):

   ```bash
   find .git -name $'Icon\r' -delete
   ```

2. `git add -A` and review `git status` — you should see ONLY: the
   `backends/px4_mavsdk/` adapter, `tests/test_backend_contract.py`, the modified
   `TODO.md` / `drone-mission/.gitignore` / `README.md` / `pyproject.toml`, any fix
   you made, and this handoff file (commit it or delete it first — either is fine).
   `.env`, `.venv/`, `media/`, and the vendor repos must NOT appear; they're
   gitignored — if any show up, stop and fix the ignore before committing.

3. Commit with a message in the style of the existing history, e.g.:
   `PX4 SITL adapter + shared backend contract suite: first live smoke flight passed (D6)`
   — include the test counts in the body.

4. `git push origin main`.

## Finish with a report

Tail of the smoke output, contract suite result, full-suite count, every file you
changed and why, and anything surprising worth recording. Put the durable facts in
`TODO.md` (step 6) — that file is the shared memory between sessions. This handoff
file is disposable once D6 is done.
