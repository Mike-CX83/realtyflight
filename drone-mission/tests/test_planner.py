"""Planner tests — no real LLM needed: FunctionModel scripts the model's
behavior deterministically, so we can prove the plumbing that matters:
the envelope is ours not the model's, repair loops feed validator messages
back, hopeless models fail honestly, and adversarial drafts die in the
validator (never in the prompt)."""

from __future__ import annotations

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from core.schema import FailsafePolicy, Limits, MissionPlan, Property
from planner import MissionPlanner, PlanRequest

# ---------------------------------------------------------------------------- #
# Scripted "models"
# ---------------------------------------------------------------------------- #


def _steps_good(center, home):
    return [
        {"action": "takeoff", "alt_m": 22.0},
        {"action": "set_gimbal", "pitch_deg": -25.0},
        {
            "action": "orbit",
            "center": center,
            "radius_m": 20.0,
            "alt_m": 22.0,
            "speed_ms": 3.0,
            "arc_deg": 360.0,
            "direction": "cw",
            "captures_every_deg": 45.0,
            "capture": {"mode": "bracket3", "tag": "exterior_orbit"},
        },
        {"action": "goto", "to": center, "alt_m": 38.0, "speed_ms": 3.0},
        {"action": "set_gimbal", "pitch_deg": -90.0},
        {"action": "capture_photo", "capture": {"mode": "single", "tag": "lot_overhead"}},
        {"action": "return_home"},
        {"action": "land"},
    ]


def scripted_model(responses: list[dict]):
    """A FunctionModel that returns each canned PlanDraft dict in order."""
    calls = {"n": 0}

    def fn(messages, info: AgentInfo) -> ModelResponse:
        idx = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        tool = (info.output_tools or [])[0].name
        return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=responses[idx])])

    return FunctionModel(fn), calls


def req(good_dict) -> PlanRequest:
    return PlanRequest(
        mission_id=good_dict["mission_id"],
        request_text="Photograph this property with a full exterior package.",
        property=Property.model_validate(good_dict["property"]),
        limits=Limits(),
        failsafe=FailsafePolicy(),
    )


# ---------------------------------------------------------------------------- #
# Happy path
# ---------------------------------------------------------------------------- #


async def test_clean_first_draft_passes(good_dict):
    center = good_dict["property"]["center"]
    home = good_dict["property"]["home"]
    model, calls = scripted_model(
        [{"summary": "Orbit package plus overhead lot shot.", "steps": _steps_good(center, home)}]
    )
    result = await MissionPlanner(model).plan(req(good_dict))

    assert result.report is not None and result.report.ok
    assert result.rounds == 1 and calls["n"] == 1
    assert isinstance(result.plan, MissionPlan)
    assert result.plan.expected_capture_count() == 9


async def test_envelope_is_ours_not_the_models(good_dict):
    """Even a cooperative model cannot author ids/limits/boundary — they come
    from the request, byte for byte."""
    center = good_dict["property"]["center"]
    model, _ = scripted_model(
        [{"summary": "ok", "steps": _steps_good(center, good_dict["property"]["home"])}]
    )
    r = req(good_dict)
    result = await MissionPlanner(model).plan(r)

    assert result.plan.mission_id == r.mission_id
    assert result.plan.property == r.property
    assert result.plan.limits == r.limits
    assert result.plan.failsafe == r.failsafe


# ---------------------------------------------------------------------------- #
# The repair loop
# ---------------------------------------------------------------------------- #


async def test_invalid_then_repaired(good_dict):
    center = good_dict["property"]["center"]
    home = good_dict["property"]["home"]
    bad = {"summary": "too high", "steps": _steps_good(center, home)}
    bad["steps"] = [dict(s) for s in bad["steps"]]
    bad["steps"][2] = dict(bad["steps"][2], alt_m=100.0)  # schema-legal, GEO-04 violation

    good = {"summary": "fixed altitude", "steps": _steps_good(center, home)}
    model, calls = scripted_model([bad, good])
    result = await MissionPlanner(model).plan(req(good_dict))

    assert result.report.ok
    assert result.rounds == 2 and calls["n"] == 2
    # the repair prompt carried the validator's exact complaint
    assert any("GEO-04" in line for line in result.transcript if line.startswith("REPAIR") or "VALIDATION" in line) or any(
        "GEO-04" in t for t in result.transcript
    )


async def test_hopeless_model_fails_honestly(good_dict):
    center = good_dict["property"]["center"]
    home = good_dict["property"]["home"]
    bad = {"summary": "stubbornly too high", "steps": _steps_good(center, home)}
    bad["steps"] = [dict(s) for s in bad["steps"]]
    bad["steps"][2] = dict(bad["steps"][2], alt_m=100.0)

    model, calls = scripted_model([bad, bad, bad])  # never fixes it
    result = await MissionPlanner(model).plan(req(good_dict))

    assert result.report is not None and not result.report.ok
    assert "GEO-04" in result.report.failed_rules()
    assert result.rounds == 3 and calls["n"] == 3  # 1 try + 2 repairs, then stop
    # and a failing report can never be approved (Wave 5 proves this elsewhere)


async def test_adversarial_intent_dies_in_validator_not_prompt(good_dict):
    """'Fly to the neighbor's yard at max speed' — the model obliges, the
    VALIDATOR kills it. Safety never depends on the prompt being persuasive."""
    center = good_dict["property"]["center"]
    home = good_dict["property"]["home"]
    evil = {"summary": "neighbor flyover", "steps": _steps_good(center, home)}
    evil["steps"] = [dict(s) for s in evil["steps"]]
    evil["steps"][3] = {
        "action": "goto",
        "to": {"lat": 36.1585, "lon": -95.9928},  # far outside the boundary
        "alt_m": 22.0,
        "speed_ms": 8.0,  # schema max, over the mission cap of 5
    }
    model, _ = scripted_model([evil, evil, evil])
    result = await MissionPlanner(model).plan(req(good_dict))

    assert not result.report.ok
    fired = set(result.report.failed_rules())
    assert {"GEO-03", "GEO-05", "KIN-01"} & fired  # geometry and speed walls


async def test_transcript_is_a_complete_audit(good_dict):
    center = good_dict["property"]["center"]
    home = good_dict["property"]["home"]
    model, _ = scripted_model(
        [{"summary": "ok", "steps": _steps_good(center, home)}]
    )
    result = await MissionPlanner(model).plan(req(good_dict))
    joined = "\n".join(result.transcript)
    assert "USER:" in joined and "DRAFT[0]" in joined and "PASS" in joined
