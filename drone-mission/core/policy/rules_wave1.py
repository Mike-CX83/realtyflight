"""Wave 1 — plan-shape rules (doc 11 §3, Wave 1).

Pure functions: MissionPlan in, list[Violation] out. Same input, same answer,
no I/O, no clock, no randomness. SCHEMA-01 (parse) lives in engine.py because
it runs *before* a MissionPlan object can exist.

SEQ-01  first step takeoff; last two return_home, land; exactly one of each
SEQ-02  step count and capture count within limits
SEQ-03  work steps only between takeoff and return_home
"""

from __future__ import annotations

from core.policy.types import Violation
from core.schema import WORK_ACTIONS, Land, MissionPlan, ReturnHome, Takeoff


def rule_seq_01_shape(plan: MissionPlan) -> list[Violation]:
    """First step is takeoff; last two are return_home then land; exactly one of each."""
    v: list[Violation] = []
    steps = plan.steps

    if not isinstance(steps[0], Takeoff):
        v.append(
            Violation(
                rule="SEQ-01",
                step=0,
                message=f"First step must be takeoff, found '{steps[0].action}'.",
                value=steps[0].action,
                limit="takeoff",
            )
        )

    if len(steps) < 3:
        v.append(
            Violation(
                rule="SEQ-01",
                message=f"A mission needs at least takeoff, return_home, land "
                f"(got {len(steps)} steps).",
                value=len(steps),
                limit=3,
            )
        )
        return v  # shape too broken for the tail checks to add signal

    if not isinstance(steps[-2], ReturnHome):
        v.append(
            Violation(
                rule="SEQ-01",
                step=len(steps) - 2,
                message=f"Second-to-last step must be return_home, found '{steps[-2].action}'.",
                value=steps[-2].action,
                limit="return_home",
            )
        )
    if not isinstance(steps[-1], Land):
        v.append(
            Violation(
                rule="SEQ-01",
                step=len(steps) - 1,
                message=f"Last step must be land, found '{steps[-1].action}'.",
                value=steps[-1].action,
                limit="land",
            )
        )

    for name, count in (
        ("takeoff", sum(isinstance(s, Takeoff) for s in steps)),
        ("return_home", sum(isinstance(s, ReturnHome) for s in steps)),
        ("land", sum(isinstance(s, Land) for s in steps)),
    ):
        if count != 1:
            v.append(
                Violation(
                    rule="SEQ-01",
                    message=f"Exactly one '{name}' step is allowed, found {count}.",
                    value=count,
                    limit=1,
                )
            )
    return v


def rule_seq_02_counts(plan: MissionPlan) -> list[Violation]:
    """Step count and expected capture count stay within the plan's limits."""
    v: list[Violation] = []
    n_steps = len(plan.steps)
    if n_steps > plan.limits.max_steps:
        v.append(
            Violation(
                rule="SEQ-02",
                message=f"Plan has {n_steps} steps; limit is {plan.limits.max_steps}.",
                value=n_steps,
                limit=plan.limits.max_steps,
            )
        )
    n_caps = plan.expected_capture_count()
    if n_caps > plan.limits.max_captures:
        v.append(
            Violation(
                rule="SEQ-02",
                message=f"Plan would capture ~{n_caps} photos; "
                f"limit is {plan.limits.max_captures}.",
                value=n_caps,
                limit=plan.limits.max_captures,
            )
        )
    return v


def rule_seq_03_ordering(plan: MissionPlan) -> list[Violation]:
    """Work steps (goto/orbit/set_gimbal/capture_photo/hold) may only appear
    strictly between the takeoff and the return_home."""
    v: list[Violation] = []
    steps = plan.steps

    takeoff_idx = next((i for i, s in enumerate(steps) if isinstance(s, Takeoff)), None)
    rth_idx = next((i for i, s in enumerate(steps) if isinstance(s, ReturnHome)), None)

    for i, step in enumerate(steps):
        if step.action not in WORK_ACTIONS:
            continue
        if takeoff_idx is None or i < takeoff_idx:
            v.append(
                Violation(
                    rule="SEQ-03",
                    step=i,
                    message=f"Step {i} ('{step.action}') appears before takeoff.",
                    value=step.action,
                )
            )
        elif rth_idx is not None and i > rth_idx:
            v.append(
                Violation(
                    rule="SEQ-03",
                    step=i,
                    message=f"Step {i} ('{step.action}') appears after return_home.",
                    value=step.action,
                )
            )
    return v
