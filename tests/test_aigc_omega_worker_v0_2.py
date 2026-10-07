from datetime import datetime, timezone

import pytest

from src.core.omega_worker_runtime import OmegaWorkerRuntime, WorkerEvent
from src.core.omega_worker_state_machine import InvalidTransition


def event(event_type: str, key: str) -> WorkerEvent:
    now = datetime.now(timezone.utc).isoformat()
    return WorkerEvent(
        event_id=f"evt-{key}",
        event_type=event_type,
        iteration_id=f"iter-{key}",
        contract_id="contract-v0.2-test",
        source="test",
        observed_at=now,
        idempotency_key=key,
    )


def test_runtime_applies_transition_and_records_evidence():
    runtime = OmegaWorkerRuntime()
    result = runtime.process(
        event("evaluate", "one"),
        {"opportunity_contract_valid"},
    )

    assert result.next_state == "EVALUATING"
    assert runtime.state == "EVALUATING"
    assert len(runtime.evidence) == 1
    assert runtime.evidence[0].guard == "opportunity_contract_valid"


def test_runtime_rejects_duplicate_idempotency_key():
    runtime = OmegaWorkerRuntime()
    first = event("evaluate", "same")
    runtime.process(first, {"opportunity_contract_valid"})

    with pytest.raises(ValueError, match="Duplicate event"):
        runtime.process(first, {"opportunity_contract_valid"})


def test_runtime_does_not_bypass_state_machine_guards():
    runtime = OmegaWorkerRuntime()

    with pytest.raises(InvalidTransition):
        runtime.process(event("evaluate", "unguarded"), set())

    assert runtime.state == "DISCOVERED"
    assert runtime.evidence == []
