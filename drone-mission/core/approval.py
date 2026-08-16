"""Approvals: the human 'yes' as a typed, hash-bound, expiring record.

The rules this module makes physically impossible:
- Approving from a static-only or failing validation report (deny-by-default).
- An approval outliving edits: it binds to compute_plan_hash(plan); change one
  meter of altitude and the hash — and the approval — no longer match.
- An approval sitting around forever: 300 s to first dispatch, then it is
  'activated' for the mission's duration (doc 08 §4 APR-01; TTL adopted from
  the MDS/Simurgh pattern).
- A sim-profile approval authorizing a physical aircraft (ENV-01, enforced in
  core/policy/dispatch.py using the fields recorded here).

Clock discipline: every function takes now_ts. Nothing here reads the wall
clock — the caller (server/executor) owns time, tests inject it.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.policy.types import ValidationReport
from core.schema import MissionPlan, compute_plan_hash

APPROVAL_TTL_S = 300.0  # unused approvals die after 5 minutes

# The exact phrase a human must type to arm a REAL aircraft (ENV-01).
REAL_FLIGHT_CONFIRMATION = "I AUTHORIZE REAL FLIGHT"

ExecutionProfile = Literal["sim", "real"]


class ApprovalError(Exception):
    """Raised when an approval cannot be granted. The message says exactly why."""


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str
    mission_id: str
    plan_hash: str
    operator: str = Field(min_length=1, max_length=120)
    profile: ExecutionProfile
    real_confirmed: bool = False          # True only if the typed phrase matched
    granted_at_ts: float
    activated_at_ts: float | None = None  # set at first dispatch; None = not yet flown

    def is_expired(self, now_ts: float) -> bool:
        """Expired = never activated and older than the TTL."""
        if self.activated_at_ts is not None:
            return False
        return (now_ts - self.granted_at_ts) > APPROVAL_TTL_S

    def activated(self, now_ts: float) -> ApprovalRecord:
        """Immutable activation at first dispatch (frozen model => new record)."""
        return self.model_copy(update={"activated_at_ts": now_ts})


def grant_approval(
    plan: MissionPlan,
    report: ValidationReport,
    *,
    operator: str,
    now_ts: float,
    profile: ExecutionProfile = "sim",
    typed_confirmation: str | None = None,
) -> ApprovalRecord:
    """The ONLY way an ApprovalRecord comes into existence.

    Refuses (raises ApprovalError) unless:
    - the report passed every rule (report.ok), AND
    - the report was live-checked (static-only reports cannot authorize flight), AND
    - for profile='real': the operator typed the exact confirmation phrase.
    """
    if not report.schema_ok:
        raise ApprovalError("Cannot approve: the plan never parsed (SCHEMA-01 failed).")
    if not report.ok:
        raise ApprovalError(
            f"Cannot approve: validation failed rules {report.failed_rules()}."
        )
    if not report.live_checked:
        raise ApprovalError(
            "Cannot approve: this report is static-only (no live telemetry/capabilities). "
            "Run validation with a connected backend first — a plan is approved against "
            "a real drone state, not on paper."
        )

    real_confirmed = False
    if profile == "real":
        if typed_confirmation != REAL_FLIGHT_CONFIRMATION:
            raise ApprovalError(
                "Real-aircraft profile requires typing the exact confirmation phrase "
                f"'{REAL_FLIGHT_CONFIRMATION}'. Refused."
            )
        real_confirmed = True

    plan_hash = compute_plan_hash(plan)
    approval_id = hashlib.sha256(
        f"{plan.mission_id}:{plan_hash}:{operator}:{now_ts:.3f}".encode()
    ).hexdigest()[:16]

    return ApprovalRecord(
        approval_id=approval_id,
        mission_id=plan.mission_id,
        plan_hash=plan_hash,
        operator=operator,
        profile=profile,
        real_confirmed=real_confirmed,
        granted_at_ts=now_ts,
    )
