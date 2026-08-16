"""The validation engine: run every registered rule, record every outcome.

Two rule tiers (doc 08 §4 two-phase design):
- STATIC rules (Waves 1-3) judge the plan alone.
- LIVE rules (Wave 4) judge the plan against the drone's current state via a
  ValidationContext (telemetry + capabilities + injected clock).

Entry points:
- parse_and_validate(raw, ctx=None)  — SCHEMA-01 then static (+ live if ctx given).
- validate_plan(plan, ctx=None)      — static (+ live if ctx given).

A report with ctx omitted is marked live_checked=False — useful for planning
and unit tests, but NEVER sufficient for approval (Wave 5 enforces that).
Deny-by-default holds inside the live rules too: missing telemetry or
capabilities is a violation, not a skip.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from core.policy import rules_wave1, rules_wave2, rules_wave3, rules_wave4
from core.policy.rules_wave4 import ValidationContext
from core.policy.types import RuleResult, ValidationReport, Violation
from core.schema import MissionPlan

Rule = Callable[[MissionPlan], list[Violation]]
LiveRule = Callable[[MissionPlan, ValidationContext], list[Violation]]

# Ordered registry: (rule_id, human description, function).
# Waves 3-5 append here — one line per new rule, nothing else changes.
RULES: list[tuple[str, str, Rule]] = [
    # Wave 1 — plan shape
    ("SEQ-01", "First step takeoff; ends return_home then land; exactly one of each",
     rules_wave1.rule_seq_01_shape),
    ("SEQ-02", "Step count and expected capture count within limits",
     rules_wave1.rule_seq_02_counts),
    ("SEQ-03", "Work steps only between takeoff and return_home",
     rules_wave1.rule_seq_03_ordering),
    # Wave 2 — numeric envelope
    ("GEO-04", "Altitudes within mission ceiling; takeoff/orbit above their floors",
     rules_wave2.rule_geo_04_altitude),
    ("KIN-01", "Speeds within the mission speed cap",
     rules_wave2.rule_kin_01_speed),
    ("KIN-02", "Orbit radius sane relative to arrival tolerance",
     rules_wave2.rule_kin_02_orbit_radius),
    ("GEO-05", "Nothing farther from home than the distance cap",
     rules_wave2.rule_geo_05_home_distance),
    # Wave 3 — boundary geometry (local meters frame + Shapely)
    ("GEO-01", "Boundary polygon is valid, non-self-intersecting, sensible area",
     rules_wave3.rule_geo_01_boundary_valid),
    ("GEO-02", "Home lies inside the boundary with margin",
     rules_wave3.rule_geo_02_home_inside),
    ("GEO-03", "Waypoints and orbit rings stay inside the boundary (3 m margin)",
     rules_wave3.rule_geo_03_flight_inside),
]

# Wave 4 — live-state rules (need a ValidationContext)
LIVE_RULES: list[tuple[str, str, LiveRule]] = [
    ("PWR-01", "Battery at/above the preflight floor, read from fresh telemetry",
     rules_wave4.rule_pwr_01_battery_floor),
    ("PWR-02", "Estimated mission time fits the usable battery budget",
     rules_wave4.rule_pwr_02_endurance),
    ("TEL-01", "Telemetry fresh; link up; GPS ready",
     rules_wave4.rule_tel_01_readiness),
    ("CAP-01", "Every step supported by the selected backend",
     rules_wave4.rule_cap_01_backend_supports_plan),
]


def validate_plan(plan: MissionPlan, ctx: ValidationContext | None = None) -> ValidationReport:
    results: list[RuleResult] = []
    for rule_id, description, fn in RULES:
        violations = fn(plan)
        results.append(
            RuleResult(
                rule=rule_id,
                description=description,
                passed=not violations,
                violations=violations,
            )
        )
    if ctx is not None:
        for rule_id, description, live_fn in LIVE_RULES:
            violations = live_fn(plan, ctx)
            results.append(
                RuleResult(
                    rule=rule_id,
                    description=description,
                    passed=not violations,
                    violations=violations,
                )
            )
    return ValidationReport(results=results, schema_ok=True, live_checked=ctx is not None)


def parse_and_validate(
    raw: str | bytes | dict[str, Any], ctx: ValidationContext | None = None
) -> tuple[MissionPlan | None, ValidationReport]:
    """SCHEMA-01 then rules. Returns (plan, report); plan is None when the raw
    input never became a MissionPlan (report then carries SCHEMA-01 violations)."""
    try:
        if isinstance(raw, (str, bytes)):
            plan = MissionPlan.model_validate_json(raw)
        else:
            plan = MissionPlan.model_validate(raw)
    except ValidationError as exc:
        violations = [
            Violation(
                rule="SCHEMA-01",
                message=_format_pydantic_error(err),
                value=_short(err.get("input")),
            )
            for err in exc.errors(include_url=False)
        ]
        report = ValidationReport(
            results=[
                RuleResult(
                    rule="SCHEMA-01",
                    description="Plan parses into the typed schema; "
                    "unknown actions/fields rejected",
                    passed=False,
                    violations=violations,
                )
            ],
            schema_ok=False,
        )
        return None, report
    except (json.JSONDecodeError, ValueError) as exc:  # malformed JSON text
        report = ValidationReport(
            results=[
                RuleResult(
                    rule="SCHEMA-01",
                    description="Plan parses into the typed schema; "
                    "unknown actions/fields rejected",
                    passed=False,
                    violations=[Violation(rule="SCHEMA-01", message=f"Not valid JSON: {exc}")],
                )
            ],
            schema_ok=False,
        )
        return None, report

    return plan, validate_plan(plan, ctx)


def _format_pydantic_error(err: dict[str, Any]) -> str:
    loc = ".".join(str(p) for p in err.get("loc", ())) or "<root>"
    return f"{loc}: {err.get('msg', 'invalid')}"


def _short(value: Any, cap: int = 60) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= cap else text[: cap - 1] + "…"
