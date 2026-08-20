# Autonomous AI Drone Capstone Context

Read this file before analyzing, planning, or modifying anything in this workspace.

## Why this workspace exists

This workspace contains five independently developed drone-related repositories. They are research inputs, not five applications that must all be merged.

Your first responsibility is to inspect all five repositories, determine what each one actually implements, reproduce important claims when practical, and identify which concepts or components from one repository could strengthen another. Do not choose a foundation solely from README claims, repository size, popularity, or the apparent sophistication of its architecture.

The intended result is a focused capstone prototype:

> A simulator-first autonomous drone system with a governed AI/LLM layer that accepts natural-language objectives, converts them into typed and validated missions, executes those missions through a real flight-control backend, and demonstrates a real-estate photography workflow.

The capstone does not need to become a finished commercial product. It must demonstrate a credible, safe, technically explainable path from natural-language intent to autonomous mission execution.

## About Mike

Mike is a software engineering and systems-design student at Atlas School in Tulsa, Oklahoma. He is an early-intermediate developer with strong systems thinking, pattern recognition, cause-and-effect reasoning, and substantial practical experience using AI coding tools to study repositories, understand unfamiliar systems, generate code, debug integrations, and compare architectures.

Do not mistake “early-intermediate developer” for inability to execute an ambitious systems-integration project. Mike does not need to invent every subsystem or memorize every framework. He is capable of assembling and adapting existing open-source systems when the work is broken into clear interfaces, testable stages, and concrete decisions.

Work with him this way:

- Explain the simple model first, then the deeper technical detail.
- Show how components connect and why a recommendation follows from the evidence.
- Give decisive recommendations when the evidence supports one.
- Use exact file paths, symbols, commands, inputs, and expected outputs.
- Separate verified facts from assumptions, README claims, and hypotheses.
- Preserve continuity and existing decisions; do not restart the project on every new discovery.
- Prefer small, working vertical slices over broad rewrites.
- Teach through the implementation so Mike can explain and defend the finished system.
- Flag genuine blockers and safety issues directly without using them as a reason to dismiss the overall project.
- Do not silently expand the scope into swarm research, drone racing, a general robotics platform, or a commercial SaaS product.

## Hardware reality

Mike owns a fully assembled **Parrot ANAFI Ai** drone. The name is ANAFI Ai, not “Afani.” It was purchased specifically to explore autonomous flight, tracking, computer vision, and photography. Custom software has not yet been installed or flown on it.

The ANAFI Ai is an available target, not an absolute architecture constraint. Mike is willing to:

- Use the ANAFI Ai through Parrot Olympe, AirSDK, and Parrot Sphinx when that path is practical.
- Keep computation on a ground computer or companion device when appropriate.
- Build or purchase a separate PX4/MAVLink-compatible drone if that produces a stronger physical implementation.
- Add a companion computer, edge-AI device, sensors, camera hardware, or other components when the architecture genuinely requires them.

Do not assume that existing software can be installed directly on the ANAFI Ai merely because both systems control drones. PX4/MAVSDK/MAVLink, ROS2, Betaflight/MSP, and Parrot Olympe/AirSDK are different integration boundaries.

Also do not assume physical rewiring is required. Prefer supported APIs and adapters first. Recommend hardware modification only when the software/API route has been examined and the tradeoff is explicit.

## Non-negotiable development strategy

This project is **simulation-first**.

No new autonomous behavior should make its first appearance on a physical aircraft. Develop and validate it in simulation, add deterministic checks and observability, and only then consider controlled physical testing.

The intended progression is:

1. Inventory and compare all five repositories.
2. Reproduce the strongest existing simulator demonstration without major modification.
3. Select a primary foundation based on verified architecture, licensing, maintainability, testability, and fit.
4. Extract or adapt only clearly useful concepts from the other repositories.
5. Create a simulator-independent mission and safety layer.
6. Demonstrate the real-estate mission in a supported simulator.
7. Add a Parrot Sphinx/Olympe backend or a physical PX4 backend.
8. Test against the corresponding simulated aircraft.
9. Move to carefully bounded physical-flight tests with manual override.

PX4 SITL with Gazebo is a valid first simulator even if the eventual aircraft is the ANAFI Ai. Parrot Sphinx is the preferred second simulator for proving that the Parrot adapter and virtual ANAFI Ai work before touching the physical drone.

## Intended architecture

The LLM is a mission interpreter and planner. It is not the flight controller and must never directly control motors, stabilization loops, or raw actuator outputs.

The target pipeline is:

```text
Natural-language objective
        ↓
Intent interpretation / approved tool selection
        ↓
Typed MissionPlan and MissionStep objects
        ↓
Deterministic mission and safety validation
        ↓
Human review / approval for flight-affecting actions
        ↓
Mission state machine and execution monitor
        ↓
DroneBackend interface
        ├── PX4/MAVSDK or ROS2 adapter → PX4 SITL/Gazebo → PX4 aircraft
        └── Parrot Olympe adapter       → Parrot Sphinx → physical ANAFI Ai
        ↓
Telemetry, camera state, completion evidence, logs, and faults
        ↺
```

The autopilot remains responsible for real-time flight stabilization. The AI layer operates at the level of constrained mission actions such as takeoff, fly-to, orbit, set gimbal, capture photo, hold, return-to-home, and land.

Prefer a backend-neutral domain layer. Flight plans, policies, safety results, mission state, and photography concepts should not be defined in PX4, ROS2, MAVSDK, MSP, or Olympe-specific types unless there is no reasonable alternative.

## Real-estate photography target

The capstone's distinguishing use case is autonomous real-estate photography—not generic natural-language drone movement.

A representative user request is:

> “Photograph this property. Orbit the house at a safe radius and altitude, keep the camera centered on the structure, capture exterior angles and roof coverage, then return home.”

The system should eventually convert that objective into an inspectable mission containing operations such as:

- Establish or confirm the property center and allowed boundary.
- Verify home position, GPS health, battery, link state, flight mode, and readiness.
- Take off to an approved altitude.
- Join an orbit smoothly rather than jumping to an arbitrary initial setpoint.
- Keep the structure framed through heading and gimbal control.
- Capture photographs at defined positions or angular intervals.
- Optionally perform exterior-elevation, roof, or overview passes.
- Track mission progress and media-capture results.
- Abort, hold, or return home on deterministic failure conditions.
- Land and associate captured media with the mission and shot list.

The prototype can begin with a known simulated property center and predefined safe boundary. Automated property-boundary discovery, advanced shot-quality scoring, photogrammetry, obstacle-aware path planning, and unattended commercial operation are later extensions unless the evidence shows they are required for the minimum demonstration.

## Minimum capstone demonstration

The preferred vertical slice is one simulated drone completing one property-photography mission:

1. An operator enters a natural-language request.
2. The LLM produces a typed, multi-step mission using only approved actions.
3. The interface displays the interpreted mission for review.
4. Deterministic code validates altitude, speed, radius, distance, geofence, battery, telemetry freshness, GPS readiness, sequence length, and required camera state.
5. The operator approves the mission.
6. The simulator executes takeoff, approach or positioning, orbit, gimbal/camera actions, return-to-home, and landing.
7. The system displays live telemetry and mission state.
8. Logs prove what was requested, what the LLM proposed, what validation changed or rejected, what the operator approved, what commands were dispatched, and what the simulator reported.
9. A manual abort/hold/RTL path interrupts active execution reliably.

Stretch success is running the same backend-neutral mission through Parrot Sphinx and then conducting a bounded physical ANAFI Ai demonstration.

## Safety and control rules

These are architectural requirements, not suggestions to place only in an LLM prompt:

- Deny execution by default when required state is missing, stale, invented, or invalid.
- Never substitute fake telemetry when a real or physical backend loses telemetry.
- Enforce constraints in deterministic code after LLM output and before dispatch.
- Parse LLM output into strict typed schemas; reject unrecognized actions and fields.
- Require explicit approval for actions that affect flight.
- Keep a final execution gate or circuit breaker immediately before backend dispatch.
- Manual pilot control and emergency actions take priority over autonomous execution.
- Abort must cancel or preempt active work; changing an internal flag is insufficient.
- Important mission failures should default to hold, abort, or RTL—not “continue.”
- Maintain altitude, speed, radius, distance-from-home, geofence, battery, GPS, link, and telemetry-freshness constraints.
- Validate coordinate frames and units at interface boundaries.
- Record immutable audit information for plans, approvals, dispatches, state changes, faults, and overrides.
- Keep simulation and physical-flight configurations visibly distinct.
- Bind control services to safe interfaces and add authentication/authorization before any physical endpoint is remotely reachable.

The capstone must remain explainable: every flight-affecting action should be traceable to an operator request, a typed plan step, passed policy checks, explicit approval, and completion evidence.

## How to analyze the five repositories

Before recommending a primary codebase, build a repository comparison matrix based on source inspection and attempted execution. For each repository, document:

### Identity and health

- Repository name, path, origin URL, default branch, current commit, and last meaningful activity.
- License file and the actual reuse/commercialization implications.
- Languages, frameworks, package managers, supported operating systems, and installation assumptions.
- Repository size, generated artifacts, vendored dependencies, and obvious maintenance risks.
- Automated tests, CI, issue state, documentation accuracy, and reproducibility.

### Architectural capabilities

- Natural-language or agent interface.
- LLM provider abstraction and whether local models are supported.
- Tool calling, schemas, or free-form parsing.
- Single-action versus durable multi-step missions.
- Deterministic policy and safety enforcement.
- Human confirmation and authorization.
- Mission state machine, cancellation, timeout, retry, and recovery behavior.
- Telemetry source, freshness checks, and completion evidence.
- Simulator and autopilot integration.
- Drone/backend abstraction quality.
- Camera, gimbal, orbit, computer vision, target tracking, and media handling.
- UI/dashboard, logging, audit, and replay capabilities.
- Tests around coordinate conversion, validation, execution, cancellation, and failure handling.

### Evidence standard

For every important claim, classify it as one of:

- **Verified in code** — cite the exact file and symbol.
- **Verified by running** — include the command and observed result.
- **Documented only** — claimed by README/docs but not yet confirmed.
- **Missing** — no implementation found.
- **Broken or inconsistent** — interfaces or claims do not connect correctly.

Do not report planned roadmap features as present capabilities. Do not infer safety enforcement merely because limits appear in prompts or configuration files.

## Cross-repository synthesis

After the inventory, identify reusable concepts by layer rather than proposing a blind repository merge.

Build a provenance table with columns similar to:

| Needed capability | Best source repo | Exact files/symbols | Reuse method | Dependencies | License | Required changes | Verification |
|---|---|---|---|---|---|---|---|

Evaluate whether one repository should provide the primary chassis while others serve as references or isolated donor components.

Potentially useful categories include:

- Governed AI/operator architecture.
- Typed action and tool registries.
- Deterministic policy engines and circuit breakers.
- Human confirmation and audit trails.
- PX4 SITL/Gazebo setup.
- MAVSDK or ROS2 flight adapters.
- Natural-language relative navigation and coordinate-frame conversion.
- YOLO/computer-vision pipelines.
- Camera and gimbal control.
- Orbit/path-generation code.
- Telemetry dashboards and mission monitoring.
- Test fixtures and simulator-based integration tests.

Prefer reimplementation behind a clean interface when copying code would import excessive dependencies, couple unrelated domains, or create license conflicts. Preserve attribution and comply with every source license.

## Known repository hypotheses to verify

Earlier research produced these working hypotheses. Treat them as leads, not facts, until the corresponding local repositories are inspected at their current commits:

- `mavsdk_drone_show`, now described as MDS/Mission-Directed Swarm, may contain the strongest governed AI/operator, policy, approval, action-monitoring, audit, dashboard, test, and PX4/MAVSDK foundation. It may also be large, swarm-oriented, and PolyForm-licensed, so scope and license boundaries matter.
- `dronesphere` may contain useful natural-language navigation, coordinate translation, MAVSDK, MCP, FastAPI, and telemetry concepts, but previously appeared to overstate deterministic safety and contained interface inconsistencies.
- `LLM-controlled-drone` may offer a simpler ROS2/PX4/Gazebo/Ollama/YOLO example and useful vision or translator concepts, but previously appeared young and weak in safety, mission state, camera operations, and tests.
- A Nanohawk/Betaflight MSP project may demonstrate a clean `prompt → JSON → safety veto → protocol` pattern, but the version previously reviewed declared a closed license and therefore should be treated as an architectural reference unless the local license says otherwise.
- The fifth repository must be discovered from the workspace. Do not guess its identity or role.

The previous frontrunner is not protected from replacement. If source inspection and reproducible tests show that another foundation is better for this capstone, explain why and update the decision.

## Recommended working method

1. Do not modify vendor/source repositories during the initial audit.
2. Locate and read every repository-level instruction file before acting.
3. Record the exact commit evaluated for each repository.
4. Run read-only static inspection first.
5. Follow each repository's documented simulation setup in an isolated environment when practical.
6. Keep a command log and capture failures exactly.
7. Create a concise architecture map and comparison matrix before proposing implementation.
8. Recommend one primary foundation, specific donor concepts, and explicit components to leave untouched.
9. Propose the smallest working vertical slice and acceptance tests.
10. Only then begin implementation in a dedicated integration repository or an explicitly approved fork/branch.

Avoid spending weeks understanding unrelated swarm, drone-show, fleet, or deployment subsystems. Trace only the paths required for one-drone natural-language mission planning, validation, simulation, telemetry, camera/gimbal control, and real-estate photography.

## Decisions the AI must not make silently

Ask Mike before:

- Abandoning the ANAFI Ai path entirely.
- Buying or specifying major new aircraft hardware.
- Choosing a source-available or restrictive license as the distributed foundation.
- Replacing the selected primary repository after implementation has started.
- Expanding the capstone to multi-drone operations, autonomous commercial deployment, or a general-purpose agent platform.
- Removing deterministic approval, validation, logging, or manual-override requirements to accelerate a demo.

Normal research, local simulation setup, tests, adapters, schemas, documentation, and reversible refactors within the agreed architecture do not require repeated confirmation.

## Definition of a strong outcome

A strong result is not “the LLM made a drone move.” It is a coherent system Mike can explain and demonstrate:

- Natural language becomes a constrained, inspectable mission plan.
- Deterministic policy decides whether that plan is safe enough to approve.
- A human remains responsible for authorizing flight.
- A mission engine executes and monitors the plan through a replaceable backend.
- A simulator proves the behavior and failure paths.
- The mission performs recognizable real-estate photography actions.
- Logs and tests make the result credible.
- The architecture provides a believable path to the ANAFI Ai or a purpose-built PX4 aircraft without rewriting the AI layer.

Optimize every recommendation for reaching that outcome with the least unnecessary complexity.

## Project memory

Three files share this project's memory. This file is the rules. `TODO.md` is the authoritative live state (done / in progress / next). `JOURNAL.md` is the narrative memory — the story so far, the challenge log (symptom → root cause → fix), and an AI context pack. New session reading order: `CLAUDE.md` → `TODO.md` → `JOURNAL.md` Part IV (Part I when you need the why behind a decision). Any session that changes something durable appends a dated entry to the journal's Part I and refreshes its Part IV. Never write secrets into any of these files.

**Story custody (Mike's call, 2026-08-20):** the IDE agent (Cursor, on Mike's Mac) is the standing custodian of the narrative record and the showcase material. Every session still writes its own journal chapter and TODO facts for work it did; the IDE agent additionally verifies — after every on-machine session and push — that `TODO.md`, `JOURNAL.md` Parts I–IV, and the tracked showcase files are current, and backfills any gaps. Presentation material (showcase pages, replay exports, demo assets) must be git-tracked or deliberately gitignored, never left untracked.

**Delegation default (same decision):** any job that can run on Mike's Mac and not in the cloud sandbox — on-machine verification, pushes, live model-API runs (the sandbox has no egress to model APIs), SITL and live drills, venv or key-dependent work, story upkeep — goes to the IDE agent via a `*_HANDOFF.md` in the repo root (house style: numbered steps, expected outputs, hard rules, report-back). Cowork sessions build and verify in the cloud, commit without pushing, and hand off.
