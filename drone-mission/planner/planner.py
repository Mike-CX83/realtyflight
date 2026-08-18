"""The mission planner: natural language -> validated MissionPlan.

Flow (doc 08 §2, FINAL §2 Q4/Q7):
  operator text + server-side envelope
    -> LLM (PydanticAI, structured output = PlanDraft: summary + steps ONLY)
    -> assemble MissionPlan (envelope injected by US, never by the model)
    -> deterministic static validation (the same engine everything uses)
    -> if violations: bounded repair loop (validator messages fed back, <=2 rounds)
    -> PlannerResult{plan, report, transcript}

Safety properties encoded here:
- The model's output type physically cannot contain mission_id, property,
  limits, or failsafe — it authors steps and a summary, nothing else.
- The planner never raises on a bad plan; it returns the failing report.
  Approval (Wave 5) is impossible on a failing or static-only report anyway.
- Provider-neutral: `model` is any PydanticAI model id ("anthropic:...",
  "openai:...", "ollama:...") or a Model instance (tests inject FunctionModel).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent

from core.policy.engine import validate_plan
from core.policy.types import ValidationReport
from core.schema import FailsafePolicy, Limits, MissionPlan, MissionStep, Property
from planner.prompts import SYSTEM_PROMPT, build_repair_prompt, build_user_prompt

MAX_REPAIR_ROUNDS = 2


class PlanDraft(BaseModel):
    """What the LLM is allowed to author. Nothing else."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    steps: list[MissionStep] = Field(min_length=1, max_length=60)


@dataclass(frozen=True)
class PlanRequest:
    mission_id: str
    request_text: str
    property: Property
    limits: Limits = field(default_factory=Limits)
    failsafe: FailsafePolicy = field(default_factory=FailsafePolicy)


@dataclass
class PlannerResult:
    plan: MissionPlan | None          # None only if no draft ever assembled
    report: ValidationReport | None   # the LAST validation report (static)
    rounds: int                       # LLM calls made (1 = first try clean)
    transcript: list[str]             # audit: what we asked, what came back


class MissionPlanner:
    def __init__(self, model, *, max_repair_rounds: int = MAX_REPAIR_ROUNDS,
                 llm_timeout_s: float = 120.0) -> None:
        self._agent = Agent(model, output_type=PlanDraft, system_prompt=SYSTEM_PROMPT)
        self._max_repairs = max_repair_rounds
        self._llm_timeout_s = llm_timeout_s

    async def plan(self, req: PlanRequest) -> PlannerResult:
        transcript: list[str] = []
        prompt = build_user_prompt(req.request_text, req.property, req.limits)
        transcript.append(f"USER: {prompt}")

        plan: MissionPlan | None = None
        report: ValidationReport | None = None
        history = None

        for round_no in range(1 + self._max_repairs):
            # D12 (review): 'the planner never raises' is now enforced, not
            # asserted — a dead API, bad model object, or hung call becomes an
            # honest failing PlannerResult inside a bounded timeout.
            try:
                run = await asyncio.wait_for(
                    self._agent.run(prompt, message_history=history),
                    timeout=self._llm_timeout_s,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                transcript.append(
                    f"MODEL-FAILURE[{round_no}]: {type(exc).__name__}: {exc}"
                )
                return PlannerResult(
                    plan=plan, report=report, rounds=round_no + 1, transcript=transcript
                )
            draft: PlanDraft = run.output
            history = run.all_messages()
            transcript.append(
                f"DRAFT[{round_no}]: {len(draft.steps)} steps — {draft.summary[:120]}"
            )

            # Assemble the full plan: the envelope comes from US, not the model.
            plan = MissionPlan(
                plan_version=1,
                mission_id=req.mission_id,
                request_text=req.request_text,
                summary=draft.summary,
                property=req.property,
                limits=req.limits,
                failsafe=req.failsafe,
                steps=draft.steps,
            )
            report = validate_plan(plan)  # static rules; live rules run at approval
            if report.ok:
                transcript.append(f"VALIDATION[{round_no}]: PASS")
                return PlannerResult(
                    plan=plan, report=report, rounds=round_no + 1, transcript=transcript
                )

            lines = [
                f"{v.rule}: {v.message}" for v in report.violations
            ][:12]
            transcript.append(f"VALIDATION[{round_no}]: FAIL {report.failed_rules()}")
            prompt = build_repair_prompt(lines)
            transcript.append(f"REPAIR-> {len(lines)} violations fed back")

        # Out of repair budget: return the failing state honestly.
        return PlannerResult(
            plan=plan, report=report, rounds=1 + self._max_repairs, transcript=transcript
        )
