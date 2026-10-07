from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .omega_worker_state_machine import OmegaWorkerStateMachine, TransitionResult


@dataclass(frozen=True)
class WorkerEvent:
    event_id: str
    event_type: str
    iteration_id: str
    contract_id: str
    source: str
    observed_at: str
    idempotency_key: str


@dataclass(frozen=True)
class EvidenceRecord:
    event_id: str
    iteration_id: str
    contract_id: str
    previous_state: str
    event: str
    next_state: str
    guard: str
    provenance: str
    fact_class: str
    recorded_at: str


class OmegaWorkerRuntime:
    """Deterministic, side-effect-free v0.2 runtime around the v0.1 state machine."""

    def __init__(self, state_machine: OmegaWorkerStateMachine | None = None):
        self.state_machine = state_machine or OmegaWorkerStateMachine()
        self.state = self.state_machine.initial_state
        self._seen_idempotency_keys: set[str] = set()
        self.evidence: list[EvidenceRecord] = []

    def process(self, event: WorkerEvent, guards: Iterable[str]) -> TransitionResult:
        if event.idempotency_key in self._seen_idempotency_keys:
            raise ValueError(f"Duplicate event: {event.idempotency_key}")

        result = self.state_machine.transition(self.state, event.event_type, set(guards))
        previous = self.state
        self.state = result.next_state
        self._seen_idempotency_keys.add(event.idempotency_key)
        self.evidence.append(
            EvidenceRecord(
                event_id=event.event_id,
                iteration_id=event.iteration_id,
                contract_id=event.contract_id,
                previous_state=previous,
                event=event.event_type,
                next_state=result.next_state,
                guard=result.guard,
                provenance=event.source,
                fact_class="FACT",
                recorded_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        return result
