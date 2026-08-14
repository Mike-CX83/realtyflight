"""Typed results of validation. Every rule outcome is recorded — pass or fail —
so the approval screen can show the operator the complete checklist (FR4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Violation(BaseModel):
    """One concrete reason a plan (or step) is not safe to approve."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: str  # e.g. "SEQ-01"
    message: str  # human-readable, names the offending value and the limit
    step: int | None = None  # 0-based index into plan.steps, when applicable
    value: float | str | None = None
    limit: float | str | None = None


class RuleResult(BaseModel):
    """The outcome of one rule over the whole plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: str
    description: str
    passed: bool
    violations: list[Violation] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """Everything the operator (and the audit log) sees about one validation run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    results: list[RuleResult]
    schema_ok: bool = True  # False => SCHEMA-01 failed and no other rules ran
    live_checked: bool = False  # True => Wave-4 live-state rules ran with real context.
    # Approval (Wave 5 / APR-01) requires ok AND live_checked — a static-only
    # report can never authorize a flight.

    @property
    def ok(self) -> bool:
        return self.schema_ok and all(r.passed for r in self.results)

    @property
    def violations(self) -> list[Violation]:
        return [v for r in self.results for v in r.violations]

    def failed_rules(self) -> list[str]:
        out = [] if self.schema_ok else ["SCHEMA-01"]
        out += [r.rule for r in self.results if not r.passed]
        return out
