# 02 — Existing Repository Inventory

**Status:** complete pending one local verification step (iCloud materialization) — 2026-08-14
**Method:** read-only inspection of `/Users/mike/Desktop/capstone_drone` via the device bridge; upstream identification and audit via GitHub (see doc 03 and RESEARCH_LOG).

---

## 1. Workspace contents (top level)

| Item | Type | Size | Notes |
|---|---|---|---|
| `AI_Autonomous_Real_Estate_Drone_Master_Architecture_Prompt.md` | file | 26 KB | Master research prompt (readable) |
| `CLAUDE.md` | file | 18 KB | Project context/instructions (readable; audited) |
| `claude-power-user/` | repo copy | 7.2 MB | Contents not materialized (see §3) |
| `dronesphere/` | repo copy | 6.3 MB | Contents not materialized |
| `FPV-Drone-AI-Agent/` | repo copy | 26 MB | Contents not materialized |
| `LLM-controlled-drone/` | repo copy | 4.4 MB | Contents not materialized |
| `mavsdk_drone_show/` | repo copy | 23 MB | Contents not materialized; `.git/shallow` present ⇒ was a `--depth 1` clone |
| `.git/` | dir | — | Root repo is `git init` only: branch `main`, **zero commits**, no remotes |
| `.DS_Store`, `Icon\r` | files | — | macOS artifacts (harmless) |

## 2. Git provenance — RESOLVED (pinned 2026-08-14, post-materialization)

Mike downloaded the iCloud contents; origins and commits are now recorded:

| Local folder | Origin (verified from .git) | Pinned local commit | Local commit date |
|---|---|---|---|
| `claude-power-user` | https://github.com/Hacker0x01/claude-power-user.git | `495f82d3054f5c8f37111311fa2086f79ba1daf4` | 2025-11-12 ("Merge branch 'obra:main'") |
| `dronesphere` | https://github.com/alireza787b/dronesphere.git | `22fc48561bbf2bc995a9a528728cb38d8e00c539` | 2025-09-30 (= upstream HEAD; repo dormant since) |
| `FPV-Drone-AI-Agent` | https://github.com/ai-in-pm/FPV-Drone-AI-Agent.git | `10e69d702b9e9c72ec0ed832a3350d7edd70f589` | 2026-03-08 (= final upstream commit) |
| `LLM-controlled-drone` | https://github.com/pratikPhadte/LLM-controlled-drone | `fc3f400bcc5ee9cc611a23ff51baa194a0640fb7` | 2026-02-25 (= final upstream commit) |
| `mavsdk_drone_show` | https://github.com/alireza787b/mavsdk_drone_show.git | `30899bedb74c6b29cb0cc83bff2ed7314c0b447d` (depth-1 shallow; hash also in `.git/shallow`; `git log` hits a Bus error through the mount but `rev-parse` works) | file mtimes 2026-08-11 ⇒ cloned days before the audit |

**Key result:** the local `mavsdk_drone_show` snapshot **contains the Simurgh Operator layer** — verified on disk: `config/agent_policy.yaml` (1,464 B), `config/agent_tools.yaml` (114,136 B), `gcs-server/agent_runtime/` (action_intent, action_planner, action_preconditions, approvals, audit, assistant, answer_composer…), `docs/guides/simurgh-operator.md`, `tests/test_agent_runtime_foundation.py`. The doc-03 audit therefore applies to the local copy, not just upstream HEAD. Three of the four dormant repos are at their final upstream commits, so upstream audit = local audit for them as well.

## 3. Blocker — RESOLVED (with a small residue)

Materialization succeeded for everything decision-relevant. A handful of individual files were still lazy-downloading at check time (`mavsdk_drone_show/CHANGELOG.md`, `dronesphere/mcp-server/core/llm_handler.py`, two READMEs/LICENSE in other repos — still `EDEADLK`). Harmless: all were already audited from upstream at the same commits. If needed later: re-run Download Now on the specific folder.

## 4. Upstream identification (high confidence for all five; evidence in doc 03)

| Local folder | Upstream (accessed 2026-08-14) | Author | License (actual file) | Upstream activity |
|---|---|---|---|---|
| `mavsdk_drone_show` | github.com/alireza787b/mavsdk_drone_show ("MDS") | Alireza Ghaderi | PolyForm Noncommercial 1.0.0 / PolyForm Small Business (+ <10-drone cap) / negotiated commercial; attribution required — **source-available, not OSI** | Very active: release v5.5.4 2026-05-16; changelog entry 2026-08-13 |
| `dronesphere` | github.com/alireza787b/dronesphere (same author) | Alireza Ghaderi | **No LICENSE file** (README claims MIT; GitHub API `license: null`) | Dormant since 2025-09-30 |
| `LLM-controlled-drone` | github.com/pratikPhadte/LLM-controlled-drone | Pratik Phadte | **No LICENSE file** (README says "MIT") | Created + abandoned 2026-02-25 (entire push history ≈ 32 min); 22 unanswered issues |
| `FPV-Drone-AI-Agent` | github.com/ai-in-pm/FPV-Drone-AI-Agent ("nanohawk-agent") | "ai-in-pm" | **Closed** per README §License + RAIL-AMS doc; vendors GPL-3.0 Betaflight headers (internal conflict) | Created + abandoned 2026-03-08 (~4 h) |
| `claude-power-user` | github.com/Hacker0x01/claude-power-user — fork of obra/superpowers | Jesse Vincent (upstream) | MIT | Fork of actively maintained upstream |

Notable: repos 1–2 share an author; `dronesphere`'s ideas were superseded by the governed "Simurgh Operator" layer inside MDS.

## 5. Duplicates, vendored copies, unrelated material

- No duplicate repos or vendored copies of each other detected at top level.
- `claude-power-user` is **not drone-related** (Claude Code skills library) — out of scope for the architecture matrix; useful as development-process tooling.
- `FPV-Drone-AI-Agent` vendors Betaflight GPL-3.0 MSP headers inside a closed-licensed repo — a license conflict in the upstream, not something we created.

## 6. Classification summary (per master prompt §6 categories; rationale in doc 03)

| Repo | Classification |
|---|---|
| `mavsdk_drone_show` | **Foundation candidate** (subject to Gate G1 license sign-off; scope = Simurgh governance layer, not the swarm subsystems) |
| `dronesphere` | **Reusable component (concepts only — reimplement)**; as a system: unsafe/misleading (README claims vs empty `validator.py` and empty tests) |
| `LLM-controlled-drone` | **Research example only** (LLM-as-flight-controller anti-pattern; small ROS2/PX4 offboard wiring reference value) |
| `FPV-Drone-AI-Agent` | **Architectural reference only** (clean prompt→typed plan→rule engine→protocol miniature; closed license bars reuse) |
| `claude-power-user` | **Redundant for the drone project** (keep as dev tooling; prefer upstream obra/superpowers) |

Nothing is recommended for deletion. Per operating constraints, **no repository will be moved, merged, modified, or removed during the research phase**; any eventual removal waits for Mike's explicit approval.

## 7. Root-repo housekeeping recommendation (no action taken)

- The root `capstone_drone` repo has zero commits. Recommend: commit `CLAUDE.md`, the master prompt, and `docs/` (this research area) so decisions are versioned; add `.gitignore` for `.DS_Store`/`Icon?`.
- After Pending-1, recommend re-cloning any repo we will actually reference at a **pinned commit** into a clearly separated `research/` directory (per master prompt §6, evaluation stays isolated from production code). Not performed in the research phase.

## 8. Open items — CLOSED 2026-08-14

- **Pending-1 ✔ resolved:** commits pinned (§2); local MDS contains Simurgh; dormant repos are at final upstream commits.
- **Pending-2 ✔ resolved:** `claude-power-user` origin confirmed as the Hacker0x01 fork (`495f82d`, merged from `obra:main` 2025-11-12).
