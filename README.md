# RealtyFlight

## Project Description

RealtyFlight turns a property photography request into an inspectable drone mission. A language model proposes typed steps, deterministic rules check the plan, an operator approves it, and a mission executor runs it through a backend while recording an audit trail.

The project explores AI assisted real estate photography through simulation. It was developed as an Atlas School capstone. The supplied demo paths run with a deterministic fake backend or PX4 software in the loop; they are not a release for unattended physical flight.

## Contents

* [Usage](#usage)
* [Installation](#installation)
* [How It Works](#how-it-works)
* [Tech Stack](#tech-stack)
* [Testing](#testing)
* [Current Limits](#current-limits)
* [Author](#author)

## Usage

A typical request is:

> Photograph this property: orbit the house and capture the exterior, then return home.

The dashboard presents the proposed steps and validation results. The operator approves the exact plan and can monitor telemetry, hold or abort a mission, and inspect recorded events afterward.

For a first look, use the scripted fake demo below. It requires no model credentials, simulator, or physical drone. Its planner is deterministic, so it demonstrates the workflow rather than unrestricted natural language understanding.

## Installation

### Prerequisites

* Git and Python 3.11 or newer.
* A Python virtual environment.
* Optional Docker and PX4/Gazebo for the simulator backend.
* Optional model provider credentials and matching PydanticAI provider extras for live language model planning.

```bash
git clone https://github.com/Mike-CX83/realtyflight.git
cd realtyflight/drone-mission
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

On Windows, activate the environment with the appropriate `.venv\Scripts` activation command.

### Scripted command line demo

From `drone-mission`:

```bash
python -m demo.fly --backend fake --model scripted
```

Review the printed plan and rule checks. Type `APPROVE` when prompted to authorize the simulated mission. The command prints its result and audit events, stored by default in `runs/mission_events.sqlite3`.

### Local dashboard

From the same folder and activated environment:

```bash
DASH_HOST=127.0.0.1 DASH_BACKEND=fake DASH_MODEL=scripted python -m server
```

Open `http://127.0.0.1:8000`. Enter the token printed in the terminal and an operator name. Plan a mission, review the checks, and approve it through the interface.

This example binds to the local computer. The repository's `phone_demo.sh` helper is a separate LAN demonstration that can start Docker, create a simulator container, and print connection details.

### Optional PX4 simulation

Start the simulator in one terminal:

```bash
docker run --rm -it jonasvautherin/px4-gazebo-headless:1.17.0
```

Then, from the activated application environment:

```bash
python -m demo.fly --backend px4 --model scripted
```

This uses the same planning and approval flow with PX4 telemetry and a simulated aircraft. Model planning can be enabled separately by selecting a supported PydanticAI model and configuring its provider. Keep keys in the ignored local environment, not in the README or Git.

## How It Works

1. **Planning:** the planner proposes steps and a summary. The application supplies the property, limits, and other governed fields.
2. **Validation:** typed schemas and policy rules check sequencing, geometry, motion limits, telemetry, and backend capabilities.
3. **Approval:** authorization is tied to the exact plan hash and has a limited lifetime.
4. **Execution:** a state machine checks dispatch conditions and uses telemetry evidence to advance steps.
5. **Audit:** SQLite events record the plan, approval, commands, state changes, and outcomes for replay.

Abort requests recovery toward home and landing; the kill circuit breaker instead freezes ordinary command dispatch. Recovery paths have their own bounded handling rather than rerunning every normal plan rule.

The `DroneBackend` interface separates the mission logic from the fake and PX4/MAVSDK implementations. The core does not import a drone SDK.

The code also contains a photography shot library, address and parcel context helpers, planner evaluation cases, and a static mission replay showcase.

## Tech Stack

* Python and Pydantic for models and validation.
* PydanticAI for structured mission proposals.
* Shapely and pymap3d for geometry.
* python-statemachine for execution states.
* MAVSDK with PX4/Gazebo for simulation.
* FastAPI, Uvicorn, and WebSockets for the dashboard.
* SQLite for mission event history.
* pytest, pytest-asyncio, and Ruff for checks.

## Testing

From `drone-mission`:

```bash
ruff check .
pytest -q
python -m evals.run --model scripted
```

The tests cover schema validation, policy rules, approvals, executor behavior, backend contracts, planner behavior, context, and dashboard routes. The scripted evaluation uses the rule engine to assess normal and adversarial cases.

Tests that require a running simulator or live external service are separately enabled. Existing test counts in older project notes are historical; this README update did not rerun the application suite or fly a mission.

## Current Limits

* The code includes fake and PX4 backends; a Parrot adapter is not included.
* PX4 demo camera output is synthetic by default. RTSP capture needs the camera extra, a compatible stream, and the matching simulator configuration.
* Address lookups depend on external data. Parcel lookup requires a configured county service.
* Simulator behavior and software controls do not establish physical flight readiness or regulatory approval.

## Project Files

* `drone-mission/core/`: schemas, policy, approvals, execution, and audit.
* `drone-mission/backends/`: fake and PX4 implementations.
* `drone-mission/planner/`: mission planning and shot library.
* `drone-mission/server/`: dashboard API and interface.
* `drone-mission/evals/`: planner evaluation harness.
* `showcase/index.html`: static replay presentation.
* [Architecture research](docs/architecture-research/08-target-system-architecture.md).
* [Development roadmap](TODO.md).
* [Historical README checkpoint](docs/README_CHECKPOINT_2026_11_16.md).

## Author

**Mike Hankins**, software engineering and systems design student at Atlas School and founder of CX83 Labs.

[GitHub](https://github.com/Mike-CX83)

## License

[MIT License](LICENSE). Third party tools and dependencies retain their respective licenses.
