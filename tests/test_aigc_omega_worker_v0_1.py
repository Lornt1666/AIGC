import json
from pathlib import Path

import pytest

from src.core.omega_worker_state_machine import InvalidTransition, OmegaWorkerStateMachine


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "aigc_omega_worker_v0_1_state_machine.json"
TRIGGER_CONFIG = ROOT / "config" / "aigc_omega_worker_v0_1_trigger_iteration.json"
MASTER_PROMPT = ROOT / "prompts" / "1JGM_AIGC_ORGANISM_MASTER_PROMPT_V0_1.md"

NEW_ITERATION_TRIGGERS = {
    "INT:GOAL_REEVALUATE",
    "INT:PLAN_RECOMPUTE",
    "INT:ASSUMPTION_CHALLENGE",
    "INT:EVIDENCE_GAP",
    "INT:CONFLICT_DETECTED",
    "INT:DRIFT_DETECTED",
    "INT:RESOURCE_THRESHOLD",
    "INT:TIME_BUDGET_WARNING",
    "INT:QUALITY_GATE",
    "INT:OWNER_GATE_REQUIRED",
}

BOUNDED_DISPOSITIONS = {
    "CONTINUE",
    "RECHECK",
    "ABORT",
    "WAIT",
    "ESCALATE",
    "BLOCK",
    "OWNER_GATE",
    "RECOVER",
    "ROLLBACK",
    "CANCEL",
    "COMPLETE",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
        ROOT / "schemas/aigc_omega_worker_v0_1/trigger_iteration.schema.json",
        CONFIG,
        TRIGGER_CONFIG,
    ]
    for path in paths:
        load_json(path)


def test_new_iteration_triggers_are_present_in_master_prompt():
    prompt = MASTER_PROMPT.read_text(encoding="utf-8")
    for trigger in NEW_ITERATION_TRIGGERS:
        assert trigger in prompt


def test_every_new_iteration_trigger_has_one_bounded_disposition():
    contract = load_json(TRIGGER_CONFIG)
    entries = {entry["trigger"]: entry for entry in contract["triggers"]}

    assert set(entries) == NEW_ITERATION_TRIGGERS
    assert set(contract["dispositions"]) == BOUNDED_DISPOSITIONS

    for trigger, entry in entries.items():
        assert entry["bounded"] is True
        assert entry["disposition"] in BOUNDED_DISPOSITIONS
        assert entry["trigger"].startswith("INT:")


def test_trigger_state_machine_events_are_real_when_declared():
    machine_config = load_json(CONFIG)
    valid_events = {transition["event"] for transition in machine_config["transitions"]}

    contract = load_json(TRIGGER_CONFIG)
    for entry in contract["triggers"]:
        for event in entry["state_machine_events"]:
            assert event in valid_events


def test_state_machine_has_bounded_destinations_for_trigger_mapped_events():
    machine_config = load_json(CONFIG)
    transitions = machine_config["transitions"]

    mapped_events = {
        event
        for entry in load_json(TRIGGER_CONFIG)["triggers"]
        for event in entry["state_machine_events"]
    }

    for event in mapped_events:
        destinations = {
            transition["to"]
            for transition in transitions
            if transition["event"] == event
        }
        assert destinations
        assert destinations <= set(machine_config["states"])
