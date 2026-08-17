"""D11 dashboard server — the thin governance window over the existing engine.

No engine logic lives here: routes call the same planner, validator, approval,
executor, and event log the terminal demo uses. See docs/architecture-research/14
for the stack decisions and the TODO D11 block for the spec.
"""

from server.app import create_app

__all__ = ["create_app"]
