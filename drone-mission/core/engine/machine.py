"""The mission state machine — doc 08 §5, expressed in python-statemachine.

Deliberately dumb: states, legal transitions, and one hook that records every
transition to the event log. ALL decision logic lives in the executor; the
machine's only job is to make illegal jumps impossible (e.g. draft -> executing
raises TransitionNotAllowed) and to leave an auditable trail.
"""

from __future__ import annotations

from collections.abc import Callable

from statemachine import State, StateMachine


class MissionMachine(StateMachine):
    # -- states (doc 08 §5) -------------------------------------------------- #
    draft = State(initial=True)
    validating = State()
    rejected = State(final=True)
    awaiting_approval = State()
    approved = State()
    executing = State()
    paused = State()
    manually_overridden = State(final=True)
    aborting = State()
    returning = State()
    landing = State()
    completed = State(final=True)
    failed = State(final=True)

    # -- transitions ---------------------------------------------------------- #
    start_validation = draft.to(validating)
    reject = validating.to(rejected) | awaiting_approval.to(rejected)
    pass_validation = validating.to(awaiting_approval)
    approve = awaiting_approval.to(approved)
    start_execution = approved.to(executing)

    step_hold = executing.to(paused)
    resume = paused.to(executing)

    operator_abort = executing.to(aborting) | paused.to(aborting)
    fault_abort = executing.to(aborting) | paused.to(aborting)
    manual_override = executing.to(manually_overridden) | paused.to(manually_overridden)

    begin_return = executing.to(returning) | aborting.to(returning)
    begin_landing = returning.to(landing) | aborting.to(landing) | executing.to(landing)
    touchdown = landing.to(completed)

    fail = (
        approved.to(failed)
        | executing.to(failed)
        | paused.to(failed)
        | aborting.to(failed)
        | returning.to(failed)
        | landing.to(failed)
    )

    def __init__(self, on_transition: Callable[[str, str, str], None] | None = None) -> None:
        self._notify = on_transition
        super().__init__()

    def on_transition(self, event: str, source: State, target: State) -> None:  # type: ignore[override]
        if self._notify is not None:
            self._notify(event, source.id, target.id)
