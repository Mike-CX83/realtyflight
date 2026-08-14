# Master Prompt: AI Autonomous Real Estate Photography Drone

You are acting as the principal systems architect, autonomous-flight engineer, robotics researcher, computer-vision engineer, full-stack architect, LLM application architect, simulation engineer, safety engineer, and open-source due-diligence lead for this project.

Your assignment is to perform a deep, evidence-based architecture and open-source investigation before we begin implementation. Do not jump directly into writing the application. First determine what the complete system must do, audit what I already collected, search broadly for additional open-source components, identify the gaps, evaluate the available hardware and simulation paths, and recommend a coherent architecture that a three-person student team can realistically demonstrate within 9 months.

## 1. Project vision

I am building a ten-month capstone centered on an AI-controlled autonomous drone system for real estate photography.

The long-term vision is a system that lets a real estate agent or photographer speak or type a desired result in ordinary language. Examples include:

1. “Create a complete exterior photo package for this property.”
2. “Orbit the house at several elevations while keeping it centered.”
3. “Capture the roof, yard, entrances, and surrounding property.”
4. “Give me a complete 360-degree view of every room.”
5. “Follow this person through the property and capture a smooth walkthrough.”
6. “Create something dramatic that emphasizes the pool, landscaping, and sunset.”

The system should understand the user’s intent and convert it into a safe, structured, reviewable photography mission. It may make bounded creative decisions about shot selection, framing, camera angle, movement, sequencing, lighting, coverage, and retakes. Creativity must stay inside the supported mission vocabulary, property boundaries, aircraft limitations, and deterministic safety rules.

The eventual platform should be capable of operating around, above, and potentially inside a property. It should understand enough about its environment to position itself, navigate, avoid obstacles, control the camera, capture the requested media, monitor mission progress, and respond safely to failures. Tracking, indoor autonomy, semantic scene understanding, 3D mapping, photogrammetry, automated shot-quality assessment, and automated editing may become stretch goals. Do not silently treat all of them as requirements for the first capstone demonstration.

The product goal is not simply “an LLM connected to a drone.” The goal is a governed autonomous photography system that gives real estate professionals creative control without requiring them to understand flight programming.

## 2. Hardware starting point, not permanent constraint

I already own a fully assembled Parrot ANAFI Ai. It was purchased for autonomous flight, tracking, computer vision, and photography. We have not installed, developed, or physically tested custom software on it yet.

The ANAFI Ai is the preferred starting platform because I already own it, but the project must not be permanently constrained by it. Evaluate it honestly rather than assuming it is either adequate or inadequate.

Determine, using current primary sources and verified technical evidence, whether the ANAFI Ai can support:

1. Professional-quality real estate still photography
2. RAW capture, exposure control, bracketing, and other useful photography controls
3. Stable professional video and controllable gimbal behavior
4. Outdoor autonomous missions
5. Indoor or GPS-denied navigation
6. Obstacle sensing and collision avoidance
7. Visual positioning, VIO, SLAM, mapping, or external localization
8. Subject and property tracking
9. Live video and telemetry access
10. Programmatic camera and flight control
11. Parrot Olympe, AirSDK, Sphinx, and any other relevant Parrot interfaces
12. Onboard, edge, or offboard computer-vision workloads
13. Safe manual override through the Skycontroller 4
14. Connection-loss handling and context-appropriate failsafes
15. The adapter architecture required to connect it to a hardware-independent core

Separate advertised specifications from capabilities that are actually exposed through supported APIs. Verify software versions, operating-system requirements, maintenance status, licensing, and compatibility. Do not assume that a feature described in marketing material is programmable.

If the ANAFI Ai is not sufficient, I am willing to build a custom drone. A custom path could allow us to select the flight controller, companion computer, camera, gimbal, depth camera, ranging sensors, positioning system, communication link, RC/manual override system, frame, motors, ESCs, and power system individually.

If a custom build is recommended, provide realistic candidate configurations and explain precisely which ANAFI limitation each added component solves. Do not recommend new hardware simply because it is newer or more flexible. The owned ANAFI path should remain the default unless evidence shows that it blocks the defined MVP or an essential architectural requirement.

## 3. Nonnegotiable control and safety model

The LLM must never function as the flight controller and must never directly control motors, raw actuators, or unconstrained movement.

The required conceptual flow is:

```text
Voice or text request
    -> intent interpretation
    -> typed MissionPlan
    -> deterministic validation and policy checks
    -> human review and approval
    -> mission state machine and execution monitor
    -> hardware-specific DroneBackend adapter
    -> supported flight controller or drone API
    -> aircraft
```

Telemetry, camera state, media results, faults, safety events, approval decisions, manual interventions, and mission history must flow back through the system and be recorded.

The system must support explicit mission states and transitions such as draft, validating, rejected, awaiting approval, approved, executing, paused, manually overridden, aborting, returning, landing, completed, and failed. The exact state model should be researched and designed rather than copied from this list without analysis.

Every flight-affecting action must be constrained by deterministic code. Relevant controls include schema validation, mission-boundary validation, altitude and speed limits, geofencing, no-fly volumes, vehicle-capability checks, battery reserves, link health, localization confidence, obstacle clearance, camera and gimbal limits, timeout handling, idempotency, retry limits, circuit breakers, emergency stop, hold, controlled landing, and return-to-home behavior where appropriate.

Manual control must always have precedence over autonomy. Investigate the correct behavior for suspending autonomous dispatch, handling queued commands, preserving mission state, and safely resuming or terminating after manual intervention. Do not assume that return to home is safe in every indoor scenario. Define context-aware failure behavior for outdoor, indoor, and GPS-denied operation.

## 4. Simulator-first development requirement

No autonomous command should be sent to the physical ANAFI Ai until the relevant behavior has been demonstrated and tested in simulation.

Research the complete current simulation landscape, not just the simulators already present in my repositories. Determine what software our hardware-independent mission system can connect to through an adapter so that the same mission can later run against a physical backend.

Compare serious candidates for:

1. Parrot-specific simulation
2. PX4 software-in-the-loop and hardware-in-the-loop simulation
3. MAVLink and MAVSDK integration
4. ROS 2 integration
5. Indoor and outdoor navigation
6. Camera and gimbal simulation
7. RGB, depth, stereo, LiDAR, IMU, GPS, and other sensor simulation
8. Collision and obstacle behavior
9. House, room, yard, and property-scale world creation
10. Photorealistic imagery where it materially benefits computer vision
11. Deterministic automated tests and headless CI
12. Fault injection, including command failure, sensor degradation, low battery, loss of localization, network loss, and manual override
13. Media capture and objective image-quality evaluation
14. Licensing, maintenance, system requirements, and practical setup burden

Evaluate options such as Parrot Sphinx, PX4 SITL, Gazebo, and any other credible current tools you discover. These names are starting points, not predetermined selections. Identify abandoned or superseded simulators and explain why they should not become the foundation.

The architecture should ideally expose a simulator-independent `DroneBackend` contract so the mission, safety, telemetry, and application layers do not have to be rewritten when moving from simulation to the ANAFI Ai or a future custom aircraft.

## 5. Open-source-first mandate

I have already collected several open-source repositories and projects related to autonomous flight, LLM-controlled drones, ROS 2, MAVLink, MAVSDK, PX4, Gazebo, YOLO, mission planning, and other drone systems. Do not assume that this existing collection is complete. It is only the starting point.

I want the deepest practical open-source investigation possible across the entire stack. Search for reusable open-source software, SDKs, APIs, libraries, protocols, models, frameworks, simulators, datasets, examples, research implementations, and reference architectures that could reduce the amount of custom code we must create.

This applies to every layer, including:

1. Web or mobile user interface
2. Microphone capture and speech-to-text
3. Natural-language interpretation
4. Local and cloud LLM abstraction
5. Structured output, tool calling, and mission-schema generation
6. Conversation and job context
7. Mission DSL, schemas, and typed command models
8. Workflow orchestration and middleware
9. Deterministic policy and safety engines
10. Approval workflows
11. Mission state machines and durable execution
12. Flight-controller and drone adapters
13. MAVLink, MAVSDK, PX4, ArduPilot, ROS 2, and Parrot integration
14. Localization, VIO, SLAM, mapping, and GPS-denied navigation
15. Path planning, trajectory generation, and motion planning
16. Obstacle detection, depth estimation, and collision avoidance
17. Object detection, segmentation, tracking, and scene understanding
18. Real-estate shot planning and computational cinematography
19. Camera, gimbal, exposure, bracketing, panorama, and media control
20. Image-quality scoring, blur detection, coverage checking, and retake logic
21. Telemetry, observability, audit logging, event storage, and replay
22. Media storage, metadata, indexing, and export
23. Authentication, authorization, secrets, API security, and network security
24. Simulation, digital twins, world generation, synthetic data, and fault injection
25. Testing, evaluation, benchmarking, and CI
26. Edge or companion-computer deployment
27. Datasets and pretrained models that are legally and technically usable

Do not stop when you find the first plausible repository. Search iteratively using multiple query families, adjacent terminology, academic references, ecosystem registries, GitHub topics, dependency graphs, related projects, forks, issues, release notes, and citations from strong repositories. Follow useful references outward.

Use a defensible saturation rule. For each major capability, attempt to identify at least three credible candidates when they exist. Continue searching until additional query families stop producing materially new, viable candidates. Record the searches performed, the date searched, and why you believe the category has reached practical saturation. Never claim that a search is literally exhaustive across the entire internet.

Open source is strongly preferred, but “open source” alone is not proof that something belongs in the stack. Prefer components that are:

1. Actively maintained
2. Documented
3. Tested
4. Compatible with the surrounding stack
5. Supported by a meaningful community or institution
6. Usable under a license compatible with this project
7. Modular enough to integrate through stable interfaces
8. Reproducible in our environment
9. Realistic for a three-person student team

For every serious candidate, verify:

1. Repository URL and canonical project home
2. Purpose and architectural role
3. License and commercial-use implications
4. Last meaningful commit and release
5. Maintenance and issue activity
6. Supported language, runtime, operating system, middleware, and hardware
7. Documentation quality
8. Test coverage or reproducibility
9. Dependency health
10. Security or safety concerns
11. Integration effort
12. Overlap with other candidates
13. Whether we should reuse the project, reuse one library or module, copy only an architectural pattern, keep it as a reference, or reject it

Do not rank repositories primarily by stars. Do not repeat README claims as verified facts. Inspect source, manifests, releases, issues, tests, examples, and official documentation. Reproduce important claims in an isolated environment when practical.

For each component we might build ourselves, explicitly state whether a suitable open-source option was found and why the candidate is or is not adequate. Custom code should exist because it is project-specific or because no compatible maintained component solves the problem, not because the search stopped early.

## 6. Audit the repositories already in this workspace

Begin with a read-only inventory of the current workspace.

1. Locate every relevant repository and project directory.
2. Record its local path, remote URL, current branch, commit hash, license, languages, frameworks, and apparent purpose.
3. Identify duplicate repositories, forks, vendored copies, abandoned experiments, generated files, and unrelated material.
4. Determine how each repository actually works by inspecting the code, not just its README.
5. Map each repository to the capability map created for this project.
6. Identify architectural conflicts, incompatible assumptions, missing safety controls, unsupported dependencies, and misleading claims.
7. Attempt reproduction only when safe and useful. Keep evaluation work isolated.

Treat the collected repositories as research inputs. Do not blindly merge them. Do not delete, rewrite, move, vendor, or combine existing repositories during the research phase. If additional candidates must be cloned for verification, place them in a clearly isolated research or temporary location and do not add them to the production codebase.

Classify every existing repository as one of the following:

1. Foundation candidate
2. Reusable component
3. Adapter reference
4. Architectural reference only
5. Research example only
6. Redundant
7. Incompatible
8. Unsafe or misleading
9. Remove from the active project, but preserve until I approve removal

## 7. Required research order

Perform the work in bounded phases. Write durable findings after each phase so the project does not lose continuity. Continue automatically between phases unless you encounter a genuinely blocking ambiguity, a required purchase, a paid service, a licensing conflict, or a decision that would fundamentally change the project.

### Phase 1: Project definition and capability map

Translate the vision into explicit functional requirements, nonfunctional requirements, safety requirements, assumptions, constraints, supported environments, and success criteria. Separate:

1. Ten-month capstone MVP
2. Near-term post-MVP capabilities
3. Long-term commercial vision

Define the vertical slice before selecting technology.

### Phase 2: Existing repository audit

Inventory and evaluate everything already collected. Produce an evidence table, reproduction notes, and a keep, isolate, replace, or remove recommendation for every repository.

### Phase 3: Gap analysis and deep open-source discovery

Compare the capability map against the existing collection. Search outward, category by category, until practical research saturation. Maintain a candidate matrix and research log with direct links and dates.

### Phase 4: Simulator and integration evaluation

Determine the best primary simulator, secondary validation environment if needed, simulator-to-core adapter, testing strategy, world requirements, and path from simulation to physical flight.

### Phase 5: Hardware decision

Evaluate the ANAFI Ai against the defined MVP and long-term requirements. Produce a go, conditional-go, or no-go recommendation. If necessary, compare realistic custom aircraft configurations without prematurely committing to a build.

### Phase 6: Target architecture

Design the complete logical and deployment architecture. Define component boundaries, ownership, interfaces, message flows, data models, mission schema, state machine, safety gates, backend contract, failure behavior, security boundaries, observability, and test seams.

### Phase 7: Ten-month execution plan

Create a milestone plan for a three-person student team. Use small, demonstrable vertical slices. Identify dependencies, critical path, risk, decision gates, acceptance tests, and the exact point at which bounded physical testing may begin.

## 8. Minimum viable capstone demonstration

The research must recommend a realistic MVP, but use the following as the baseline candidate:

1. A user enters or speaks a bounded real-estate photography request.
2. Speech is converted to text if voice is used.
3. The LLM converts the request into a typed, schema-valid `MissionPlan` composed only of supported mission primitives.
4. Deterministic software validates the mission against vehicle capability, environment, geofence, altitude, speed, battery, connectivity, and safety rules.
5. The application explains the proposed mission in plain language.
6. A human approves or rejects it.
7. The execution engine runs it in simulation through a backend adapter.
8. The dashboard shows mission state, telemetry, camera state, and safety events.
9. The system captures simulated photos or video and associates them with mission steps.
10. Hold, abort, manual override, link loss, and safe recovery behaviors are demonstrated.
11. The complete request, plan, validation results, approval, commands, telemetry, faults, media, and outcome are stored in replayable logs.

A representative first mission could be: orbit a simulated property at a validated altitude, keep the house centered, capture eight exterior images plus one overhead image, and return safely. Research may improve this example, but it must preserve a bounded, testable end-to-end demonstration.

Indoor room-by-room autonomy is important to the product vision, but it should only be included in the MVP if the research shows that GPS-denied localization, obstacle sensing, indoor failsafes, camera performance, and simulator support are achievable by this team within ten months. Otherwise, define it as a specific next-stage milestone rather than quietly pretending it is solved.

## 9. Required architectural questions

Your final recommendation must answer at least these questions:

1. What is the exact ten-month MVP?
2. What capabilities are deliberately deferred, and why?
3. What should run in the browser, backend, edge computer, companion computer, flight controller, and simulator?
4. Does the LLM need to run locally, in the cloud, or through a provider-neutral interface?
5. What is the typed mission representation?
6. What mission primitives are permitted?
7. How is a creative request converted into deterministic executable steps?
8. What validates the mission independently of the LLM?
9. What requires human approval?
10. How are state, retries, timeouts, cancellation, and recovery handled?
11. What happens during manual override?
12. What happens when the network, GPS, localization, perception, camera, or individual command fails?
13. How do indoor and outdoor failsafes differ?
14. What is the backend contract shared by simulators and physical drones?
15. Which simulator should be primary, and why?
16. Can Parrot Sphinx or another environment validate the actual ANAFI path?
17. Can the ANAFI Ai meet the photography and autonomy requirements?
18. If not, what custom hardware is justified?
19. Which existing repositories should remain?
20. Which newly discovered projects should be adopted, studied, or rejected?
21. What custom middleware must we create?
22. How will media quality and mission success be evaluated objectively?
23. How will the system be tested automatically before physical flight?
24. What are the highest technical, licensing, safety, schedule, and integration risks?
25. What evidence would cause us to change the recommended architecture?

## 10. Required deliverables

Create or update a dedicated research documentation area without modifying the production implementation. Use a clear structure equivalent to:

```text
docs/architecture-research/
    00-project-charter-and-scope.md
    01-capability-map-and-requirements.md
    02-existing-repository-inventory.md
    03-existing-repository-audit.md
    04-open-source-landscape.md
    05-simulator-comparison.md
    06-anafi-ai-capability-assessment.md
    07-custom-hardware-options.md
    08-target-system-architecture.md
    09-mvp-and-ten-month-roadmap.md
    10-risk-register-and-decision-gates.md
    RESEARCH_LOG.md
    FINAL_RECOMMENDATION.md
```

Adapt filenames only if the repository already has an established documentation convention.

The final package must include:

1. Executive summary in plain language
2. Capability map
3. Current-repository inventory and disposition matrix
4. Open-source candidate catalog by architectural layer
5. Evidence-based comparison tables
6. License and maintenance-risk summary
7. Simulator decision matrix
8. ANAFI Ai go, conditional-go, or no-go assessment
9. Custom-hardware alternatives if justified
10. Proposed system-context and component diagrams
11. End-to-end request, approval, execution, and telemetry sequence
12. Mission schema and state-machine proposal
13. Safety architecture and failure-mode table
14. Recommended technology stack with primary choice, fallback, and rationale for every layer
15. Explicit list of custom software we still need to build
16. MVP definition and stretch-goal boundary
17. Ten-month roadmap for three students
18. Risk register and decision gates
19. Reproducible research log with sources, dates, commands, and assumptions
20. Final list of repositories to keep, add, isolate, or eventually remove

Use compact diagrams where relationships or flows are clearer visually, but do not substitute diagrams for interface definitions and evidence.

## 11. Evidence and reasoning standards

Use current primary sources whenever possible:

1. Official product and SDK documentation
2. Canonical source repositories
3. Source code and manifests
4. Release notes and changelogs
5. Issue trackers and discussions
6. Maintainer statements
7. Peer-reviewed papers or authoritative technical reports

Clearly label statements as:

1. Verified fact
2. Repository or vendor claim not independently verified
3. Technical inference
4. Recommendation
5. Open question requiring a test

Include direct links and the date accessed. When information conflicts, explain the conflict and identify the stronger evidence. Do not fabricate features, compatibility, benchmark results, licenses, maintenance status, or successful reproduction.

Make decisive recommendations. Do not respond with an unranked list of possibilities. For each architectural layer, identify:

1. Recommended primary choice
2. Best fallback
3. Rejected alternatives
4. Reason for the decision
5. Evidence confidence
6. Integration cost and risk

Explain technical decisions in plain language first, then provide the deeper implementation detail. Assume I understand systems and cause-and-effect relationships but am still developing my software implementation experience.

## 12. Operating constraints

1. Research and architecture come before implementation.
2. Do not delete or merge repositories during this phase.
3. Do not purchase, recommend purchasing, or commit us to hardware or paid services without identifying the need, alternatives, cost, and decision gate.
4. Do not let the LLM directly control flight.
5. Do not use “AI autonomous” as vague language. Define exactly which intelligence exists, where it runs, what inputs it receives, what outputs it may produce, and what deterministic system constrains it.
6. Do not design a general-purpose drone that can literally do anything. Preserve the broad long-term vision while defining a bounded vocabulary of supported capabilities for each development stage.
7. Prefer reusable open-source components, but do not create an unstable pile of frameworks merely to maximize the number of dependencies.
8. Favor stable interfaces and replaceable adapters over tight coupling.
9. Prefer a small working vertical slice over a broad collection of unfinished features.
10. Keep the core hardware-independent wherever practical.
11. Preserve a human approval point and manual override throughout the architecture.
12. Treat safety, observability, testability, licensing, and reproducibility as architectural requirements, not final-stage additions.
13. Exclude drone racing and unrelated Atlas team planning.

## 13. Start now

Begin by performing the read-only workspace inventory and writing the project capability map. Then create a phased research plan based on the actual repositories and environment you find.

Do not give me a shallow one-response answer. Work through the investigation in bounded chunks, persist the evidence after each phase, and keep following credible open-source leads until each major capability reaches practical research saturation. When the research is complete, return a decisive architecture recommendation and a clear explanation of exactly what we should build first.
