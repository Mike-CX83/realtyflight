"""The dispatch gate — the last wall before any command reaches a backend
(doc 08 §4: 'final circuit breaker'; doc 11 Wave 5).

The executor calls check_dispatch() immediately before EVERY flight-affecting
command. It re-verifies, cheaply, everything that could have changed since
approval:

APR-01   a recorded approval exists, matches this exact plan (hash), belongs to
         this mission, and is unexpired (300 s to first dispatch)
ENV-01   the sim/real wall: a physical aircraft requires the 'real' profile AND
         a typed-confirmation approval; profile and approval must agree; sim
         configuration can never reach a real drone
LIVE     the Wave-4 rules run again with current telemetry (battery, freshness,
         link, GPS, capabilities) — approval is a snapshot, reality moves

Plus the CircuitBreaker: a manual latch (kill switch). Once tripped, nothing
dispatches until a human resets it — state changes alone are never enough
(doc 00 §3, CLAUDE.md safety rules).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.approval import ApprovalRecord
from core.policy.engine import LIVE_RULES
from core.policy.rules_wave4 import ValidationContext
from core.policy.types import Violation
from core.schema import MissionPlan, compute_plan_hash


@dataclass(frozen=True)
class DispatchContext:
    """Everything the gate needs, injected — the gate reads no globals, no clock."""

    now_ts: float
    profile: str  # "sim" | "real" — the RUNNING configuration's profile
    approval: ApprovalRecord | None
    live: ValidationContext  # telemetry + capabilities, same type Wave 4 uses


class CircuitBreaker:
    """Manual latch in front of the backend. trip() opens it (with a recorded
    reason); only an explicit human reset() closes it again."""

    def __init__(self) -> None:
        self._open_reason: str | None = None
        self._trip_log: list[str] = []

    @property
    def is_open(self) -> bool:
        return self._open_reason is not None

    @property
    def open_reason(self) -> str | None:
        return self._open_reason

    @property
    def trip_log(self) -> list[str]:
        return list(self._trip_log)

    def trip(self, reason: str) -> None:
        self._open_reason = reason
        self._trip_log.append(reason)

    def reset(self, *, operator: str) -> None:
        self._trip_log.append(f"reset by {operator}")
        self._open_reason = None


def rule_apr_01_approval(plan: MissionPlan, dctx: DispatchContext) -> list[Violation]:
    a = dctx.approval
    if a is None:
        return [Violation(rule="APR-01", message="No approval on record. Nothing dispatches.")]

    v: list[Violation] = []
    if a.mission_id != plan.mission_id:
        v.append(
            Violation(
                rule="APR-01",
                message=f"Approval belongs to mission '{a.mission_id}', not '{plan.mission_id}'.",
                value=a.mission_id,
                limit=plan.mission_id,
            )
        )
    current_hash = compute_plan_hash(plan)
    if a.plan_hash != current_hash:
        v.append(
            Violation(
                rule="APR-01",
                message="The plan changed after approval (hash mismatch). "
                "Every edit requires a fresh approval.",
                value=current_hash[:12],
                limit=a.plan_hash[:12],
            )
        )
    if a.is_expired(dctx.now_ts):
        age = dctx.now_ts - a.granted_at_ts
        v.append(
            Violation(
                rule="APR-01",
                message=f"Approval expired: granted {age:.0f} s ago and never used "
                "(limit 300 s to first dispatch). Re-approve.",
                value=round(age, 0),
                limit=300,
            )
        )
    return v


def rule_env_01_profile_wall(plan: MissionPlan, dctx: DispatchContext) -> list[Violation]:
    v: list[Violation] = []
    caps = dctx.live.capabilities

    if caps is None:
        return [
            Violation(
                rule="ENV-01",
                message="Cannot verify sim/real status: no backend capabilities. "
                "Denied by default.",
            )
        ]

    if caps.is_physical:
        if dctx.profile != "real":
            v.append(
                Violation(
                    rule="ENV-01",
                    message=f"Backend '{caps.name}' is a PHYSICAL aircraft but the running "
                    f"profile is '{dctx.profile}'. Sim configuration can never touch a real drone.",
                    value=dctx.profile,
                    limit="real",
                )
            )
        if dctx.approval is not None and not dctx.approval.real_confirmed:
            v.append(
                Violation(
                    rule="ENV-01",
                    message="Physical aircraft requires an approval granted with the typed "
                    "real-flight confirmation phrase. This approval lacks it.",
                )
            )

    if dctx.approval is not None and dctx.approval.profile != dctx.profile:
        v.append(
            Violation(
                rule="ENV-01",
                message=f"Approval was granted for profile '{dctx.approval.profile}' but the "
                f"running profile is '{dctx.profile}'. Profiles must match.",
                value=dctx.profile,
                limit=dctx.approval.profile,
            )
        )
    return v


def check_dispatch(
    plan: MissionPlan, dctx: DispatchContext, breaker: CircuitBreaker | None = None
) -> list[Violation]:
    """Run the full pre-dispatch gate. Empty list = clear to send the command."""
    v: list[Violation] = []

    if breaker is not None and breaker.is_open:
        v.append(
            Violation(
                rule="CB-01",
                message=f"Circuit breaker is OPEN ({breaker.open_reason}). "
                "A human must reset it before anything dispatches.",
            )
        )

    v += rule_apr_01_approval(plan, dctx)
    v += rule_env_01_profile_wall(plan, dctx)

    # Reality re-check: the Wave-4 live rules, with current state.
    for _rule_id, _desc, live_fn in LIVE_RULES:
        v += live_fn(plan, dctx.live)

    return v
