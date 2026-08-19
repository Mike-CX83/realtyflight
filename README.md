# RealtyFlight

**A sentence becomes a governed, auditable drone photography mission.**

Capstone project — Atlas School, Tulsa. An operator types
*"Photograph this property: orbit the house, full exterior package."* — a
large-language-model planner proposes a typed mission, deterministic safety
rules judge it, a human approves it, and a state-machine executor flies it on
a real autopilot, producing photos and an append-only audit trail that can
replay the entire flight.

```
natural language
      ↓
LLM planner            — proposes typed steps ONLY; cannot touch limits,
      ↓                  boundaries, ids, or the aircraft (server-injected)
deterministic rules    — 15+ validators: sequence, envelope, boundary
      ↓                  geometry incl. path corridors, live battery/GPS/
      ↓                  telemetry freshness, backend capability
human approval         — hash-bound to the exact plan, 300 s TTL; editing
      ↓                  one meter of altitude voids it
mission executor       — 13-state machine; a dispatch gate re-checks reality
      ↓                  before EVERY command; steps advance only on
      ↓                  telemetry EVIDENCE; abort preempts and flies home
DroneBackend contract  — the core cannot tell PX4 from Parrot from a test
      ↓                  fake; that is the portability claim, proven by one
      ↓                  contract suite run against every backend
PX4 (MAVSDK) → Gazebo physics simulation
```

## What is real vs. simulated

| Real | Simulated |
|---|---|
| PX4 autopilot firmware (the same software that flies physical aircraft) | The aircraft & world (Gazebo physics) |
| MAVLink/MAVSDK protocol, telemetry, flight modes | GPS constellation, battery model |
| The LLM planner (verified live against gpt-5.1) | Camera frames on low-power machines (synthetic evidence stubs; real RTSP frames verified, full camera flights pending GPU hardware) |
| Every safety rule, approval, audit record | — |

**No physical aircraft flies this code yet — by design.** Physical flight sits
behind explicit gates (simulator-proven behavior, fault drills, a Part
107-certificated remote pilot in command, and a typed real-flight
confirmation). The `sim`/`real` profile wall is enforced in code: a simulation
configuration can never command a physical aircraft.

## The safety boundary

The LLM **proposes**; it never controls. Its output is parsed into a closed,
typed vocabulary (unknown actions and fields are parse failures). Everything
that decides whether the aircraft moves is deterministic code Mike can point
to: the rule engine, the hash-bound approval, the pre-dispatch gate, the
circuit breaker, and the evidence-gated executor. Five real integration bugs
have been caught so far — each by a different deterministic layer, which is
the architecture working as intended.

## Status (2026-08-15)

Safety core, executor, LLM planner, PX4 adapter, shot library, and the
end-to-end demo are built and tested: **180 passed, 6 skipped** (the skips are
SITL-gated contract tests), lint-clean. A full mission — sentence → approval →
Gazebo flight → 10 photos → 48-event audit trail — has run live. Current work
is tracked honestly in [`TODO.md`](TODO.md); research and architecture
decisions live in [`docs/architecture-research/`](docs/architecture-research/).

## Demo

`./phone_demo.sh` — phone demo in one command (`--fake` for instant, no Docker).

## One-command demo (no API key, no simulator)

```bash
cd drone-mission
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m demo.fly --backend fake --model scripted --auto-approve
```

## The real thing (LLM + physics + watchable map)

```bash
# terminal 1 — the drone (PX4 + Gazebo, headless):
docker run --rm -it jonasvautherin/px4-gazebo-headless:1.17.0

# terminal 2 — the mission (put ANTHROPIC_API_KEY or OPENAI_API_KEY in drone-mission/.env):
cd drone-mission && source .venv/bin/activate
python -m demo.fly "Photograph this property: the full exterior package." --backend px4
```

Open QGroundControl alongside and watch the mission fly on a live map; press
Ctrl+C mid-orbit to watch the abort path bring it home. `docs/DEMO.md` (in
progress) carries the full show script.

## Repository map

```
drone-mission/          the software (core, backends, planner, demo, tests)
docs/architecture-research/   14 research docs: charter → audit → architecture → roadmap
TODO.md                 the living plan — every milestone, decision, and parked item
research/               third-party reference repos (read-only, gitignored)
```

## Tests

```bash
cd drone-mission && pytest -q          # 180 passed, 6 skipped
RUN_PX4_CONTRACT=1 pytest tests/test_backend_contract.py -q   # with a live SITL
```

CI runs the suite + ruff on every push (`.github/workflows/ci.yml`).

## License

MIT (see [LICENSE](LICENSE)). Third-party reference repositories under
`research/` keep their own licenses and are never redistributed here.
