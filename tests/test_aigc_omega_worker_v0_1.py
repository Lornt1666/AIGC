import json
from pathlib import Path

import pytest

from src.core.omega_worker_state_machine import InvalidTransition, OmegaWorkerStateMachine


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "aigc_omega_worker_v0_1_state_machine.json"


def test_state_machine_definition_is_closed():
    machine = OmegaWorkerStateMachine(CONFIG)
    assert machine.initial_state == "DISCOVERED"
    assert "PAID" in machine.terminal_states
    assert set(machine.states) == {
        "DISCOVERED","EVALUATING","APPROVED","APPLYING","ENGAGED","EXECUTING",
        "VERIFYING","DELIVERED","PAID","LEARNED","REJECTED","BLOCKED",
        "ESCALATED","FAILED","ROLLED_BACK","CANCELLED"
    }


def test_valid_transition_requires_guard():
    machine = OmegaWorkerStateMachine(CONFIG)
    result = machine.transition("DISCOVERED", "evaluate", {"opportunity_contract_valid"})
    assert result.next_state == "EVALUATING"


def test_invalid_event_is_rejected():
    machine = OmegaWorkerStateMachine(CONFIG)
    with pytest.raises(InvalidTransition):
        machine.transition("DISCOVERED", "submit", {"anything"})


def test_failed_guard_is_rejected():
    machine = OmegaWorkerStateMachine(CONFIG)
    with pytest.raises(InvalidTransition):
        machine.transition("DISCOVERED", "evaluate", set())


def test_terminal_state_cannot_continue_normally():
    machine = OmegaWorkerStateMachine(CONFIG)
    with pytest.raises(InvalidTransition):
        machine.transition("PAID", "learn", {"outcome_record_complete"})


def test_emergency_stop_is_global_guard():
    machine = OmegaWorkerStateMachine(CONFIG)
    result = machine.transition("EXECUTING", "emergency_stop", {"runtime_emergency_stop_active"})
    assert result.next_state == "BLOCKED"


def test_contract_files_are_valid_json():
    paths = [
        ROOT / "schemas/aigc_omega_worker_v0_1/task_contract.schema.json",
        ROOT / "schemas/aigc_omega_worker_v0_1/opportunity_contract.schema.json",
        ROOT / "schemas/aigc_omega_worker_v0_1/evidence_record.schema.json",
        ROOT / "schemas/aigc_omega_worker_v0_1/revenue_record.schema.json",
        ROOT / "schemas/aigc_omega_worker_v0_1/state_machine.schema.json",
        CONFIG,
    ]
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))
