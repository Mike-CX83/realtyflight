"""Planner eval harness (TODO C3 second half / D15).

Deterministic exam for the natural-language planner: golden cases judge
intent-match, adversarial cases judge what becomes executable, the real rule
engine is the scorer, and independent probes re-check every survivor.

Keyless run: `python -m evals.run`. Live: `python -m evals.run --model <id>`.
NOTE: running requires the dev extra `pydantic-evals` (pip install -e ".[dev]").
This package carries no flight authority — it only ever calls the planner and
the validator, never a backend.
"""

from evals.dataset import CASE_IDS, CASES, EVAL_PROPERTY, PROBES, Expect, PlanCaseInputs
from evals.scoring import PlanOutcome, aggregate, classify

__all__ = [
    "CASES",
    "CASE_IDS",
    "EVAL_PROPERTY",
    "Expect",
    "PROBES",
    "PlanCaseInputs",
    "PlanOutcome",
    "aggregate",
    "classify",
]
