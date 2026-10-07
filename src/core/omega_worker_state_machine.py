from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_MACHINE = PROJECT_ROOT / "config" / "aigc_omega_worker_v0_1_state_machine.json"


class InvalidTransition(ValueError):
    pass


@dataclass(frozen=True)
class TransitionResult:
    previous_state: str
    event: str
    next_state: str
    guard: str


class OmegaWorkerStateMachine:
    """Deterministic contract/state transition engine for AIGC-Ω Worker v0.1.

    This module only evaluates state transitions. It performs no external actions.
    """

    def __init__(self, config_path: str | Path = DEFAULT_STATE_MACHINE):
        self.config_path = Path(config_path)
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.version = data["version"]
        self.initial_state = data["initial_state"]
        self.terminal_states = frozenset(data["terminal_states"])
        self.states = frozenset(data["states"])
        self.transitions = tuple(data["transitions"])
        self._validate_definition()

    def _validate_definition(self) -> None:
        if self.initial_state not in self.states:
            raise ValueError("Initial state is not declared.")
        for state in self.terminal_states:
            if state not in self.states:
                raise ValueError(f"Terminal state is not declared: {state}")
        for transition in self.transitions:
            source = transition["from"]
            target = transition["to"]
            if source != "*" and source not in self.states:
                raise ValueError(f"Unknown transition source: {source}")
            if target not in self.states:
                raise ValueError(f"Unknown transition target: {target}")
            if not transition.get("event") or not transition.get("guard"):
                raise ValueError("Every transition requires event and guard.")

    def allowed_transitions(self, state: str) -> list[dict]:
        if state not in self.states:
            raise InvalidTransition(f"Unknown state: {state}")
        return [
            t for t in self.transitions
            if t["from"] in {state, "*"}
        ]

    def transition(self, state: str, event: str, guards: set[str]) -> TransitionResult:
        if state not in self.states:
            raise InvalidTransition(f"Unknown state: {state}")
        if state in self.terminal_states and event != "emergency_stop":
            raise InvalidTransition(f"Terminal state {state} cannot transition on {event!r}.")

        candidates = [
            t for t in self.transitions
            if t["from"] in {state, "*"} and t["event"] == event
        ]
        if not candidates:
            raise InvalidTransition(f"No transition from {state!r} on event {event!r}.")

        for transition in candidates:
            guard = transition["guard"]
            if guard in guards:
                return TransitionResult(
                    previous_state=state,
                    event=event,
                    next_state=transition["to"],
                    guard=guard,
                )

        required = ", ".join(t["guard"] for t in candidates)
        raise InvalidTransition(
            f"Guard failed for {state!r} on {event!r}; required guard(s): {required}"
        )
