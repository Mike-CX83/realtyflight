# 15 — Health Check & Stack Audit

**Status:** run 2026-08-16 by the Cowork session, **independently** — fresh
re-sync of the repo at commit `1b31b73` (local == origin, working tree clean)
into a clean cloud environment; every number below re-measured there, not
quoted from earlier reports.

## Scorecard

| Dimension | Result | Verdict |
|---|---|---|
| Test suite | **180 passed, 6 skipped** (SITL-gated contract tests) | ✅ |
| Live verification | D6–D10 all flown/re-certified on real SITL (JOURNAL ch. 10–15) | ✅ |
| Branch coverage (pytest-cov) | core/policy 91–100% per file; schema, geo, shots, planner 100%; events 97%, machine 97%, dispatch 98%; **executor 83%**; overall 80% | ✅ (see debts) |
| Lint (ruff, repo-wide) | **0 findings** | ✅ |
| Types (mypy) | 41 advisory findings, 7 files — documented, not CI-gated | 🟡 debt |
| Security (pip-audit) | **Runtime deps: 0 known vulns.** One tooling finding: `setuptools 79.0.1` (PYSEC-2026-3447, fixed ≥ 83) — venv build tool, not imported by shipped code | 🟡 one-liner fix |
| Dependency freshness | Everything current except `pydantic-ai-slim` 2.30 → 2.31 (minor) | ✅ |
| Lockfile | `requirements.lock` present (reference env) | ✅ |
| CI | `.github/workflows/ci.yml`: checkout → py3.11 → install → ruff → pytest, on push + PR; runs green | ✅ |
| Repo hygiene | Private ✓ · noreply commit identity ✓ · battle-tested .gitignore ✓ · no secrets in tree (audited twice) ✓ | ✅ |
| Documentation | Root README (claims re-verified true), living TODO, **JOURNAL: 15-chapter build narrative + milestone table + challenge log**, research docs 00–14 | ✅ |

## Stack, layer by layer

| Layer | Choice | Version/state | Verdict |
|---|---|---|---|
| Language | Python | 3.11 (CI-pinned) | ✅ current LTS-grade |
| Schemas | pydantic | v2 | ✅ |
| LLM layer | pydantic-ai-slim (provider-neutral) | 2.30 (2.31 avail.) | ✅ minor bump optional |
| Flight SDK | MAVSDK-Python | v3 (bundles mavsdk_server) | ✅ |
| Autopilot | PX4 SITL v1.17 via `jonasvautherin/px4-gazebo-headless:1.17.0` | digest pinned in JOURNAL | ✅ (remember `-t`) |
| Physics | Gazebo 8.11 (in-image) | — | ✅ |
| Geometry | shapely 2 + pymap3d | current | ✅ |
| State machine | python-statemachine | current; `current_state` → `configuration` deprecation warnings | 🟡 migrate in a quiet moment |
| Tests | pytest 8 + pytest-asyncio | current | ✅ |
| Lint | ruff | current, clean | ✅ |
| Licenses | MIT/BSD/Apache deps only; PolyForm/GPL material read-only or external | ✅ commercial-clean (B5) |

## Debts & risks (honest, ranked)

1. **Repo lives on iCloud-synced Desktop** — the single biggest operational
   risk; it caused evictions, git bus errors, a stale lock, and pip stalls
   twice this week. *Recommendation: move the repo to `~/code/` (outside
   Desktop/Documents) at the next quiet moment; one `git clone` + folder swap.*
2. **Docker disk cap** — confirm it is actually set (~40 GB) after the purge;
   an unlimited cap already ate the disk once.
3. **Executor branch coverage 83%** — untested branches are mostly deep
   recovery permutations and SITL-only paths; acceptable now, worth one
   targeted test pass during M4 fault drills.
4. **mypy 41 advisory** — burn down opportunistically, then add to CI.
5. **setuptools upgrade** — `pip install -U "setuptools>=83"` in each venv.
6. **python-statemachine deprecation** — rename `current_state` uses before a
   future major removes it.
7. **Planner eval set** — M2 acceptance wants ≥ 20 adversarial requests via
   pydantic-evals (C3 tail); current adversarial set is smaller.
8. **QGC demo handoff** — still pending; pure upside for demo-readiness.
9. **Open decisions:** B2 teammates · B4 real showcase date · B6 mapping-
   mission capture-cap (needed before D13 rung 1).
10. **Parked with wired circle-back:** D8 live camera flights → A7 (Linux/RTX box).

## Re-run this audit anytime

```bash
cd drone-mission && source .venv/bin/activate && pip install -e ".[dev]"
pytest -q                                   # expect 180 passed, 6 skipped
ruff check .                                # expect clean
pytest -q --cov=core --cov-branch           # core files ≥ 83%
python -m mypy core backends planner demo   # advisory count
pip install -q pip-audit && pip-audit -l    # security
python -m demo.fly --backend fake --model scripted --auto-approve  # exit 0
```

## Verdict

The build is **healthy at every layer that matters**: independently reproduced
green suite, live-verified flight stack, zero lint, zero runtime-dependency
vulnerabilities, green CI, honest docs, and a license posture that keeps the
commercial path open. The debts are real but small, named, and scheduled — and
notably, none of them are architectural: the two risks that actually bit this
week (iCloud, Docker's disk) are *environmental*, and both have concrete
remediations above. The architecture itself — language proposes, rules decide,
a human authorizes, a state machine flies, on any backend that speaks the
contract — has now survived five milestones, six real bugs, one external
review, and two machines without needing a redesign. Companion wireframe:
`16-architecture-wireframe.html`.
