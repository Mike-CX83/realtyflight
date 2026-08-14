# 11 — Safety Core Build Plan (the rules we write ourselves)

**Status:** ✅ **EXECUTED — all five waves shipped 2026-08-14** (same day as planned, ahead of the M1 schedule): 15 rules + approval service + dispatch gate + circuit breaker, 122 passing tests, ~20 evil scenarios. Code: `drone-mission/core/`. This document remains as the design record; deviations from plan were minor (contract types placed in `core/interfaces.py` instead of `backends/base.py` so the dependency arrow only points backends→core; Wave-4/5 rules take injected clocks and contexts — no wall-clock reads anywhere in the core).

---

## 1. What we're building, in plain words

One Python function at heart: **`validate(plan, live_status) → report`**. It receives the mission the LLM proposed plus what the drone currently reports (battery, GPS, telemetry age), runs every rule, and returns a report listing each rule with pass or fail and the exact number that broke it. If anything fails, the mission cannot be approved. The same rules run a second time, step by step, during flight (the "dispatch gate"), so a mission that was safe at approval can still be stopped if reality changed.

## 2. Borrowed vs written

| Borrowed (libraries do the hard part) | Written by us (the actual rules) |
|---|---|
| Pydantic — rejects malformed plans automatically | ~15 rule functions, each 5–20 lines |
| Shapely — "is this point inside the polygon" math | The rule that *calls* it with the right buffer |
| pymap3d — GPS coords → flat meters conversion | Choosing home as the frame center |
| python-statemachine — state mechanics | Which states/transitions are allowed |
| pytest — test runner | The pass/fail example tables |

Every rule is a pure function: same inputs → same answer, no surprises, each one unit-tested. Total estimate: **~250 lines of rules + ~400 lines of tests**, built over ~3 weeks of M1 alongside the schema.

## 3. Build order — five waves (each wave = working code + green tests before the next)

### Wave 1 — Plan-shape rules (day 1–2; no math, pure logic — the confidence builder)
| Rule | Plain English | Example failure it catches |
|---|---|---|
| SCHEMA-01 | The plan must parse into our exact types; unknown actions or extra fields = instant reject | LLM invents `"action": "barrel_roll"` |
| SEQ-01 | First step is takeoff; last two are return_home then land; exactly one of each | Plan that lands twice, or never comes home |
| SEQ-02 | At most 40 steps and 60 photos | LLM writes a 500-step marathon |
| SEQ-03 | No flying steps before takeoff or after return_home | `goto` after `land` |

### Wave 2 — Number-limit rules (day 3–4; simple comparisons)
| Rule | Plain English | Catches |
|---|---|---|
| GEO-04 | Every altitude ≤ the mission ceiling (default 40 m sim / 120 m legal max); takeoff ≥ 5 m | "orbit at 200 meters" |
| KIN-01 | Every speed ≤ 8 m/s (the ANAFI obstacle-avoidance envelope) | "as fast as possible" |
| KIN-02 | Orbit radius between 8 and 100 m | 2 m radius death-spiral |
| GEO-05 | Nothing farther from home than the distance cap (default 150 m) | Drifting off to the neighbor's lot |

### Wave 3 — Geometry rules (week 2; the Shapely wave — most interesting)
| Rule | Plain English | Catches |
|---|---|---|
| GEO-01 | The boundary polygon must be a sane shape (≥3 corners, doesn't cross itself, reasonable size) | Operator draws a bow-tie polygon |
| GEO-02 | Home must be inside the boundary | Launching from outside the property |
| GEO-03 | Every waypoint AND the whole orbit circle stay inside the boundary, with a 3 m safety margin | Orbit circle that clips the fence line |
Key trick (already decided): convert GPS coordinates to flat meters centered on home *first* (pymap3d), then let Shapely do plane geometry. This one conversion function gets the most brutal tests in the project.

### Wave 4 — Live-state rules (week 3; first rules that read the drone, not the plan)
| Rule | Plain English | Catches |
|---|---|---|
| PWR-01 | Battery ≥ 30% before takeoff — read from *fresh* telemetry, deny if data is missing or stale | Approving on yesterday's battery reading |
| PWR-02 | Rough time math: mission duration must fit inside a conservative battery budget | 25-minute plan on a 20-minute battery |
| TEL-01 | Telemetry older than 2 s → no dispatch; GPS not ready → no takeoff | Flying blind on frozen data |
| CAP-01 | Every step must be something the selected backend actually supports | bracket5 on a backend that can't |

### Wave 5 — Execution gates (built with the state machine, late M1)
| Rule | Plain English |
|---|---|
| APR-01 | No dispatch without a recorded approval that matches this exact plan (hash) and hasn't expired (5 min) |
| ENV-01 | Real-aircraft mode requires the separate real-flight config + typed confirmation — sim settings can never touch the real drone |

## 4. One worked example, so the shape is concrete (GEO-04)

```python
def rule_geo_04_altitude(plan: MissionPlan) -> list[Violation]:
    v = []
    for i, step in enumerate(plan.steps):
        alt = getattr(step, "alt_m", None)
        if alt is not None and alt > plan.limits.max_alt_m:
            v.append(Violation(
                rule="GEO-04", step=i,
                message=f"Step {i} altitude {alt} m exceeds ceiling {plan.limits.max_alt_m} m",
                value=alt, limit=plan.limits.max_alt_m))
    return v
```
That's a complete safety rule. Fifteen of these, a loop that runs them all, and a report class — that's the brain.

## 5. Testing approach (built *with* each wave, not after)

- Table-driven: each rule gets a table of (input plan, expected result) — minimum 1 pass case + 2 fail cases; geometry rules get edge cases (point exactly on the boundary line).
- The **evil-requests file**: ~10 adversarial missions kept in `tests/evil_plans/` — "fly to the neighbor's yard at 200 m," "skip landing," "orbit at 30 m/s" — every one must die in the validator with the right rule ID. This file later doubles as the live demo where you type an evil request on stage and the report lights up red.
- Definition of done for the safety core: all rules implemented + tested, evil file fully rejected, validator wired into the approval screen so failures are visible in the UI, and every constant (40 m, 8 m/s, 30%…) lives in one config block — no magic numbers buried in code.

## 6. Where this sits in the schedule

This is the heart of **roadmap M1 (October)**, right after the schema exists (TODO D3): Wave 1–2 in week one, Wave 3 in week two, Wave 4 in week three, Wave 5 alongside the state machine. Claude pair-writes every wave; you should be able to explain any rule in one sentence, because each one *is* one sentence.
