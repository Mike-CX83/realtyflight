# LAPTOP_SETUP — the Linux/RTX box becomes the flight lab

You are the Cursor agent on Mike's Clevo/Sager NH58AF (RTX 2070), Linux side.
This machine exists for ONE project: RealtyFlight. Read `CLAUDE.md` and
`TODO.md` in this repo before acting — they are binding. Work phase by phase
and REPORT to Mike between phases. Never touch the Windows partition. Never
commit `.env`. 3-strikes rule: the same error after 3 distinct fix attempts →
stop and write it up.

## Phase 1 — System state & updates (report, then act)

1. Inventory first, verbatim into your report:
   `lsb_release -a` (Sphinx needs Ubuntu 20.04/22.04/24.04 x86_64 — TODO A1),
   `mokutil --sb-state` (want SecureBoot disabled — TODO A2; if enabled, that
   is a BIOS change MIKE makes manually — report it, don't attempt),
   `nvidia-smi` (want RTX 2070 + driver version — TODO A3),
   `df -h /`, `free -h`, `python3 --version`.
2. Update everything: `sudo apt update && sudo apt full-upgrade -y`, then
   `sudo ubuntu-drivers install` if nvidia-smi failed, reboot if kernel/driver
   changed, re-verify nvidia-smi.
3. Install the base kit:
   `sudo apt install -y git curl gh build-essential docker.io python3-venv python3-pip`
   `sudo usermod -aG docker $USER` (relogin/newgrp for it to take effect).
   If Ubuntu 24.04 (python3 = 3.12): also add deadsnakes python3.11
   (`sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install -y python3.11 python3.11-venv`)
   — the repo runs on ≥3.11, but Parrot Olympe (later, A5/C1) requires 3.9–3.11.

## Phase 2 — Disk audit: REPORT BEFORE DELETING (Mike's rule)

1. Produce `CLEANUP_REPORT.md` (repo root, gitignored is fine — or just paste
   it to Mike): `du -xh -d 2 ~ 2>/dev/null | sort -rh | head -30`, plus
   `ollama list` if Ollama exists, plus any old project/VM/dataset directories
   with sizes. For each entry: KEEP or DELETE recommendation + why.
2. **KEEP by default (do not delete):** Ollama and ALL its model weights (it
   is the planned M8 defense-day fallback ON THIS MACHINE — doc 14 §6),
   NVIDIA/CUDA anything, and anything you cannot identify.
3. Delete NOTHING until Mike replies approving the list. Then delete only
   what he approved and show `df -h /` before/after.

## Phase 3 — The repo

1. `gh auth login` (HTTPS + browser; Mike logs in — the repo is PRIVATE).
2. `mkdir -p ~/code && cd ~/code && gh repo clone Mike-CX83/realtyflight`
   — `~/code`, deliberately NOT a synced/Desktop folder (hard-won Mac lesson).
3. Git identity on this machine:
   `git config user.name "Mike Hankins" && git config user.email "216079163+Mike-CX83@users.noreply.github.com"`
4. `cd realtyflight/drone-mission && python3 -m venv .venv && source .venv/bin/activate`
   `pip install -e ".[dev,camera]" && pip install "pydantic-ai-slim[anthropic,openai]"`
5. **MIKE-INPUT:** `drone-mission/.env` (the API key) is gitignored and must be
   carried over by hand — USB stick or retyped. Scripted-model steps below work
   without it; live-LLM steps need it.
6. Verify the clone cold: `pytest -q` and `ruff check .` — the pass count must
   match the number stated in TODO.md's newest D-entry. Mismatch = STOP, report.

## Phase 4 — Flight stack on native Linux

1. QGroundControl (Linux AppImage, per qgroundcontrol.com Ubuntu docs):
   `sudo usermod -aG dialout $USER && sudo apt remove -y modemmanager` (their
   standard prereqs), download the AppImage, `chmod +x`, launch once.
2. SITL sanity (plain vehicle):
   `docker run -d -t --rm --name px4sitl jonasvautherin/px4-gazebo-headless:1.17.0`
   (the `-t` matters — JOURNAL ch. 15/16), then
   `python -m backends.px4_mavsdk.smoke` → expect SMOKE FLIGHT COMPLETE, and
   `RUN_PX4_CONTRACT=1 pytest tests/test_backend_contract.py -q` → 12 passed.
3. Dashboard sanity: `DASH_BACKEND=fake DASH_MODEL=scripted python -m server`
   → open the printed URL in the laptop browser, run one scripted mission via
   the page. (Phone test rides on the same Wi-Fi later.)

## Phase 5 — A7: the D8 CIRCLE-BACK (the reason this laptop exists)

Follow TODO A7 exactly — this is the parked real-camera flight:
1. `docker rm -f px4sitl; docker run -d -t --rm --name px4sitl -p 8554:8554 jonasvautherin/px4-gazebo-headless:1.17.0 -v gz_x500_mono_cam`
2. While it flies, log `nvidia-smi` + CPU load — we want the evidence that this
   box erases the Mac's mono_cam CPU ceiling.
3. `python -m demo.fly "Photograph this property: orbit the house, full exterior package." --backend px4 --camera rtsp`
   (add `--model scripted --auto-approve` if `.env` hasn't arrived yet).
4. **PASS = mission completed AND every new `media/*.jpg` > 5 KB AND every
   sidecar says `"camera_mode": "rtsp"`.** Then: tick **D8 → [x]** and **A7**
   in TODO.md, note the machine + load numbers, `rm D8_HANDOFF.md`, commit in
   house style, push. (If it fails HERE, the Mac's CPU wasn't the whole story —
   record everything, reopen the D8 deferred options, report.)

## Phase 6 — OPTIONAL if time & energy remain: Sphinx (TODO A5/A6)

Attempt Parrot Sphinx install per developer.parrot.com/docs/sphinx —
log every step and error verbatim into JOURNAL.md (this install is known to be
finicky; that log IS the deliverable). Success = virtual ANAFI Ai hovering in
the `empty` world. 3-strikes applies; an honest failure report is a fine
outcome for today.

## Final report to Mike

Phase-by-phase: system inventory, what was updated, the cleanup report +
before/after disk, suite counts, SITL + contract + smoke results, the A7
verdict with GPU/CPU evidence, dashboard check, Sphinx outcome if attempted,
and every TODO/JOURNAL edit committed and pushed.
