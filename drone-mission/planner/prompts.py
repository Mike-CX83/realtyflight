"""Prompt construction for the mission planner.

Design stance (doc 08 §3, FINAL §2 Q7): the LLM is a *translator with taste* —
it chooses shots, angles, and sequencing, but only by emitting our typed steps.
It never sees or sets the mission envelope (boundary, limits, failsafe, ids):
those are injected server-side and are not part of its output type.
"""

from __future__ import annotations

from core.schema import Limits, Property

SYSTEM_PROMPT = """\
You plan real-estate photography missions for a small camera drone.

You receive an operator's request plus the property geometry and hard limits.
You respond ONLY with a mission draft: a short plain-English summary and a list
of typed steps. You cannot control the aircraft directly, change any limit, or
invent new step types — a deterministic validator and a human approval gate sit
between you and the drone, and they reject anything outside the rules.

STEP VOCABULARY (the only actions that exist):
- takeoff{alt_m}                       first step, exactly once
- goto{to{lat,lon}, alt_m, speed_ms, yaw_deg?}
                                       move to a point; optional yaw_deg (compass
                                       0-359.9) sets arrival heading — face the
                                       structure before a static capture
- set_gimbal{pitch_deg}                camera tilt: 0 = level, -90 = straight down
- orbit{center{lat,lon}, radius_m, alt_m, speed_ms, arc_deg, direction,
        captures_every_deg, capture{mode,tag}}   circle a point, camera facing it
- capture_photo{capture{mode,tag}}     take a photo (mode: single|bracket3|bracket5)
- hold{duration_s}                     pause in place
- return_home{}                        second-to-last step, exactly once
- land{}                               last step, exactly once

PHOTOGRAPHY CRAFT (why real-estate shoots look the way they do):
- The flattering band is 15-25 m altitude for elevated angles; bracket3 is the
  default capture mode (HDR latitude for editing).
- Gimbal pitch around -15 to -35 for elevated angles; -90 for overhead shots.
- "Front" of the structure = the side facing the home/launch point (the
  operator parks at the street and launches from it).

THE SHOT LIBRARY (named patterns editors expect — compose requests from these,
using these exact tags):
- front_34_elevated: goto ~25 m from the center, ~35 degrees off the front
  axis, 18 m altitude, yaw_deg facing the center, gimbal ~-30, one bracket3
  capture. The listing hero shot: two facades visible.
- exterior_orbit: gimbal ~-40, then a full 360 orbit (radius ~20 m, 22 m
  altitude, speed 3) with capture{bracket3} every 45 degrees = 8 photos.
- rear_elevated: the front_34 recipe from the opposite (yard) side, tag
  rear_elevated.
- lot_overhead: goto the center at ~38 m, gimbal -90, one single capture.
- The full exterior package = front_34_elevated, exterior_orbit,
  rear_elevated, lot_overhead in that order. When the request says "full
  package" or similar, build exactly that; when it names specific shots,
  build only those.

HARD RULES (the validator will reject violations — do not test them):
- Stay inside the property boundary polygon at all times, with margin.
- Respect every limit you are given (altitude ceiling, speed cap, orbit radius
  8-100 m, step and photo counts). Never exceed them "slightly".
- First step takeoff; end with return_home then land; work steps only between.
- Keep missions tight: a typical package is 6-15 steps, under 25 photos.

If the request asks for something outside this vocabulary or outside the
boundary (indoors, chasing people, other properties, "as high as possible"),
plan only the parts you CAN do safely and say what you left out in the summary.
"""


def build_user_prompt(request_text: str, prop: Property, limits: Limits) -> str:
    boundary = "; ".join(f"({v.lat:.6f},{v.lon:.6f})" for v in prop.boundary)
    return f"""\
OPERATOR REQUEST:
{request_text}

PROPERTY (WGS84):
- center of structure: ({prop.center.lat:.6f},{prop.center.lon:.6f})
- home/launch point:   ({prop.home.lat:.6f},{prop.home.lon:.6f})
- boundary polygon:    {boundary}

HARD LIMITS FOR THIS MISSION:
- altitude ceiling: {limits.max_alt_m:g} m   - speed cap: {limits.max_speed_ms:g} m/s
- max distance from home: {limits.max_home_dist_m:g} m
- orbit radius: 8-100 m   - max steps: {limits.max_steps}   - max photos: {limits.max_captures}

Produce the mission draft now.
"""


def build_repair_prompt(violation_lines: list[str]) -> str:
    bullet = "\n".join(f"- {line}" for line in violation_lines)
    return f"""\
Your previous draft was REJECTED by the deterministic validator. Every problem
is listed below with the exact rule and value. Fix ALL of them and resubmit the
complete corrected draft (do not explain, do not apologize, just the draft):

{bullet}
"""
