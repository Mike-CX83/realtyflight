"""Run the planner eval harness.

Keyless (CI mode — scripted FunctionModel, proves the harness itself):

    python -m evals.run

Against a live model (any PydanticAI model id; keys via drone-mission/.env):

    python -m evals.run --model openai:gpt-5.1
    python -m evals.run --model anthropic:claude-sonnet-4-5
    python -m evals.run --model ollama:llama3.2 --kind golden

Every case runs through the REAL MissionPlanner (same repair loop, same
server-injected envelope) against the standard eval property, is judged by
the REAL rule engine, then re-checked by the dataset's independent probes.
Results print as a table and land as a JSON artifact under runs/evals/
(gitignored, like every runtime output).

Exit codes: 0 ok; 2 the safety alarm — an UNEXPECTED executable_violation
(or the scripted run failed to reproduce its seeded a10 alarm, which means
the alarm circuit itself is broken).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from core.schema import FailsafePolicy, Limits
from evals.dataset import CASES, EVAL_PROPERTY, Expect, PlanCaseInputs
from evals.models import build_scripted_model
from evals.scoring import (
    MODEL_FAILURE,
    PlanOutcome,
    aggregate,
    classify,
    outcome_from_result,
)
from planner.demo import _load_dotenv
from planner.planner import MissionPlanner, PlanRequest

SEEDED_VIOLATIONS = {"a10"}  # the scripted model's deliberate alarm test


@dataclass
class GovernedOutcome(Evaluator[PlanCaseInputs, PlanOutcome, Expect]):
    """Thin pydantic-evals wrapper around scoring.classify()."""

    def evaluate(
        self, ctx: EvaluatorContext[PlanCaseInputs, PlanOutcome, Expect]
    ) -> dict[str, Any]:
        assert ctx.metadata is not None
        label, acceptable, reasons = classify(ctx.output, ctx.metadata)
        return {
            "outcome": label,
            "acceptable": EvaluationReason(value=acceptable, reason="; ".join(reasons) or None),
            "rounds": float(ctx.output.rounds),
        }


def _selected(kind: str) -> list[tuple[PlanCaseInputs, Expect]]:
    if kind == "all":
        return CASES
    return [(i, e) for i, e in CASES if e.kind == kind]


async def run_eval(
    model_spec: str = "scripted",
    *,
    kind: str = "all",
    max_concurrency: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any], Any]:
    """-> (rows, aggregates, pydantic-evals EvaluationReport)."""
    model = build_scripted_model() if model_spec == "scripted" else model_spec
    planner = MissionPlanner(model)
    cases = _selected(kind)
    outcomes: dict[str, PlanOutcome] = {}

    async def task(inputs: PlanCaseInputs) -> PlanOutcome:
        started = time.monotonic()
        result = await planner.plan(
            PlanRequest(
                mission_id=f"EVAL-{inputs.case_id}",
                request_text=inputs.request_text,
                property=EVAL_PROPERTY,
                limits=Limits(),
                failsafe=FailsafePolicy(),
            )
        )
        outcome = outcome_from_result(inputs.case_id, result, started)
        outcomes[inputs.case_id] = outcome
        return outcome

    dataset = Dataset(
        name="realtyflight-planner",
        cases=[Case(name=i.case_id, inputs=i, metadata=e) for i, e in cases],
        evaluators=(GovernedOutcome(),),
    )
    report = await dataset.evaluate(
        task,
        name=f"realtyflight-planner:{model_spec}",
        max_concurrency=max_concurrency,
        progress=False,
    )

    rows: list[dict[str, Any]] = []
    for inputs, expect in cases:
        outcome = outcomes.get(inputs.case_id)
        if outcome is None:  # the task itself died before the planner returned
            label, acceptable = MODEL_FAILURE, expect.kind != "golden"
            reasons = ["task never produced an outcome"]
            rounds, ok, failed, wall_s, captures = 0, False, [], 0.0, None
        else:
            label, acceptable, reasons = classify(outcome, expect)
            rounds, ok, failed = outcome.rounds, outcome.ok, outcome.failed_rules
            wall_s = outcome.wall_s
            captures = (
                outcome.plan.expected_capture_count() if outcome.plan is not None else None
            )
        rows.append(
            {
                "case_id": inputs.case_id,
                "kind": expect.kind,
                "request_text": inputs.request_text,
                "label": label,
                "acceptable": acceptable,
                "reasons": reasons,
                "rounds": rounds,
                "ok": ok,
                "failed_rules": failed,
                "captures": captures,
                "wall_s": wall_s,
            }
        )
    return rows, aggregate(rows), report


def write_artifact(
    path: Path, model_spec: str, kind: str, rows: list[dict[str, Any]], agg: dict[str, Any]
) -> None:
    payload = {
        "meta": {
            "harness": "evals/run.py v1 (D15)",
            "model": model_spec,
            "kind": kind,
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "aggregates": agg,
        "rows": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _print_report(model_spec: str, rows: list[dict[str, Any]], agg: dict[str, Any]) -> None:
    print(f"\nPLANNER EVAL — model: {model_spec}\n")
    print(f"{'case':6} {'kind':12} {'outcome':22} {'rnd':>3}  first reason")
    for r in rows:
        first = r["reasons"][0] if r["reasons"] else ""
        print(f"{r['case_id']:6} {r['kind']:12} {r['label']:22} {r['rounds']:>3}  {first[:70]}")
    print()
    if agg["golden_total"]:
        rate = f"{agg['golden_pass_rate'] * 100:.1f}%"
        print(
            f"golden:      {agg['golden_pass']}/{agg['golden_total']} pass ({rate}), "
            f"{agg['golden_first_try_clean']} first-try clean"
        )
    if agg["adversarial_total"]:
        print(f"adversarial: {agg['adversarial_safe']}/{agg['adversarial_total']} safe")
    print(f"avg rounds:  {agg['avg_rounds']}")
    if agg["model_failures"]:
        print(f"model failures: {agg['model_failures']}")
    if agg["executable_violations"]:
        print(f"EXECUTABLE VIOLATIONS: {agg['executable_violations']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="scripted",
                        help='"scripted" (keyless) or a PydanticAI model id')
    parser.add_argument("--kind", default="all", choices=["all", "golden", "adversarial"])
    parser.add_argument("--max-concurrency", type=int, default=4)
    parser.add_argument("--out", default=None, help="JSON artifact path (default runs/evals/)")
    args = parser.parse_args()

    _load_dotenv()  # same tiny loader the demo uses; real env vars win
    rows, agg, _report = asyncio.run(
        run_eval(args.model, kind=args.kind, max_concurrency=args.max_concurrency)
    )
    _print_report(args.model, rows, agg)

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    safe_model = args.model.replace(":", "_").replace("/", "_")
    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[1] / "runs" / "evals" / f"{stamp}_{safe_model}.json"
    )
    write_artifact(out, args.model, args.kind, rows, agg)
    print(f"\nartifact: {out}")

    violations = set(agg["executable_violations"])
    seeded = SEEDED_VIOLATIONS if args.model == "scripted" and args.kind != "golden" else set()
    unexpected = violations - seeded
    missing_seed = seeded - violations
    if unexpected:
        print(f"\nALARM: unexpected executable violations: {sorted(unexpected)}")
        return 2
    if missing_seed:
        print(f"\nALARM: seeded violation not reproduced (alarm circuit broken): "
              f"{sorted(missing_seed)}")
        return 2
    if seeded:
        print("\nnote: a10 is the SEEDED violation — it proves the alarm circuit works and "
              "documents the missing transit-altitude rule (Mike's policy call).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
