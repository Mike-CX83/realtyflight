"""Try the planner against a REAL model from your terminal.

    export ANTHROPIC_API_KEY=...        (or OPENAI_API_KEY=...)
    python -m planner.demo "Photograph this property, orbit the house, full package"

Falls back to telling you what to set if no key is present. Uses the same
test property as the unit suite; swap in real coordinates when you like.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from core.schema import FailsafePolicy, GeoPoint, Limits, Property
from planner import MissionPlanner, PlanRequest


def _load_dotenv() -> None:
    """Tiny .env loader (repo root or cwd) — keys stay on disk, gitignored,
    never in shell history. Real env vars win over the file."""
    for candidate in (Path(__file__).resolve().parents[1] / ".env", Path(".env")):
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
            return


_load_dotenv()

TEST_PROPERTY = Property(
    center=GeoPoint(lat=36.1540, lon=-95.9928),
    boundary=[
        GeoPoint(lat=36.15450, lon=-95.99330),
        GeoPoint(lat=36.15450, lon=-95.99230),
        GeoPoint(lat=36.15350, lon=-95.99230),
        GeoPoint(lat=36.15350, lon=-95.99330),
    ],
    home=GeoPoint(lat=36.15360, lon=-95.99320),
)


def pick_model() -> str | None:
    """Explicit override first (PLANNER_MODEL), then whichever key exists."""
    if os.environ.get("PLANNER_MODEL"):
        return os.environ["PLANNER_MODEL"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic:claude-sonnet-4-5"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai:gpt-5.1"  # override with PLANNER_MODEL=openai:<model> if needed
    return None


async def main() -> None:
    text = " ".join(sys.argv[1:]) or "Photograph this property: full exterior package."
    model = pick_model()
    if model is None:
        print("No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY and re-run.")
        print("(Local option: install Ollama and use model string 'ollama:<model>'.)")
        return

    print(f"model: {model}\nrequest: {text}\n")
    planner = MissionPlanner(model)
    result = await planner.plan(
        PlanRequest(
            mission_id="DEMO0000000000000000000000",
            request_text=text,
            property=TEST_PROPERTY,
            limits=Limits(),
            failsafe=FailsafePolicy(),
        )
    )

    print(f"rounds: {result.rounds}")
    if result.plan:
        print(f"\nSUMMARY: {result.plan.summary}\n\nSTEPS:")
        for i, s in enumerate(result.plan.steps):
            print(f"  {i:2d}. {s.model_dump(exclude_none=True)}")
    if result.report:
        verdict = "PASS — ready for approval screen" if result.report.ok else "FAIL"
        print(f"\nVALIDATION ({verdict}):")
        for r in result.report.results:
            mark = "ok " if r.passed else "FAIL"
            print(f"  [{mark}] {r.rule}: {r.description}")
            for v in r.violations:
                print(f"         -> {v.message}")


if __name__ == "__main__":
    asyncio.run(main())
