from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from src.coordination import CoordinationEngineeringRequest, engineer_coordination_plan


def request_payload() -> dict[str, object]:
    return {
        "request_id": "COORD-REQ-ENGINE001",
        "objective": "Coordinate a verified local AIGC design iteration.",
        "state": {
            "state_id": "COORD-STATE-ENGINE001",
            "revision": 3,
            "artifact_refs": ["repo://AIGC/README.md"],
            "values": {"phase": "design", "verified_checks": 12},
        },
        "iteration": {
            "current_iteration": 1,
            "maximum_iterations": 4,
            "minimum_progress_delta": 0.05,
            "no_progress_limit": 2,
        },
        "tools": [
            {
                "tool_id": "TOOL-LOCAL-INSPECT",
                "function_name": "repository.inspect",
                "purpose": "Inspect a bounded local repository projection.",
                "parameters": {"path": "src"},
                "expected_outputs": {"inventory": "array"},
                "effect_class": "READ_LOCAL",
                "maximum_calls_per_iteration": 2,
            },
            {
                "tool_id": "TOOL-LOCAL-VERIFY",
                "function_name": "verification.run",
                "purpose": "Verify a local candidate artifact.",
                "expected_outputs": {"verification": "object"},
                "effect_class": "PURE",
            },
        ],
        "agents": [
            {
                "agent_id": "AGT-DESIGNER",
                "role": "AUTO_DESIGNER",
                "mandate": "Design the requested bounded coordination artifact.",
                "capabilities": ["architecture"],
                "assigned_tool_ids": ["TOOL-LOCAL-INSPECT"],
                "output_contract": "coordination design candidate",
                "verification_function": "verification.design",
            },
            {
                "agent_id": "AGT-VERIFIER",
                "role": "INDEPENDENT_VERIFIER",
                "mandate": "Independently verify the candidate against acceptance criteria.",
                "capabilities": ["verification"],
                "assigned_tool_ids": ["TOOL-LOCAL-VERIFY"],
                "depends_on_agent_ids": ["AGT-DESIGNER"],
                "output_contract": "verification receipt",
                "verification_function": "verification.independent",
            },
        ],
        "coordination": {
            "strategy": "HIERARCHICAL_DAG",
            "maximum_parallel_agents": 2,
            "fail_fast": True,
            "require_independent_verification": True,
        },
        "acceptance_criteria": [
            "request contract validates",
            "receipt proves zero egress",
        ],
    }


def test_coordination_plan_is_deterministic_bounded_and_zero_egress():
    request = CoordinationEngineeringRequest.model_validate(request_payload())
    first = engineer_coordination_plan(request)
    second = engineer_coordination_plan(request)

    assert first == second
    assert first["schema_version"] == "aigc.coordination-engineering-receipt.v1"
    assert first["endpoint"] == "POST /v1/coordination/engineer"
    assert first["terminal_status"] == "PASS"
    assert first["verification"]["result"] == "PASS"
    assert first["multi_agent_coordination"]["waves"] == [
        {"wave": 0, "agent_ids": ["AGT-DESIGNER"]},
        {"wave": 1, "agent_ids": ["AGT-VERIFIER"]},
    ]
    assert first["iteration"]["maximum_tool_calls_per_iteration"] == 3
    assert first["iteration"]["maximum_tool_calls_over_plan"] == 12
    assert first["transition_proposal"]["status"] == "PROPOSED_NOT_APPLIED"
    assert first["alpha_plan"]["terminal_status"] == "PASS"
    assert first["production_ready"] is False
    assert first["authority_granted"] is False
    assert first["external_actions_performed"] == 0
    assert first["tool_dispatches_performed"] == 0
    assert first["provider_calls_performed"] == 0
    assert first["memory_writes_performed"] == 0


def test_execution_request_stops_at_the_plan_only_boundary():
    payload = request_payload()
    payload["execution_requested"] = True
    receipt = engineer_coordination_plan(CoordinationEngineeringRequest.model_validate(payload))

    assert receipt["terminal_status"] == "BLOCKED"
    assert receipt["verification"]["first_blocker"] == "ENDPOINT_PLAN_ONLY"
    assert receipt["external_actions_performed"] == 0
    assert receipt["authority_granted"] is False


def test_consequential_tool_is_classified_and_blocked_without_authority():
    payload = request_payload()
    payload["tools"] = [
        {
            "tool_id": "TOOL-INVOICE-SEND",
            "function_name": "finance.invoice.send",
            "purpose": "Propose sending an invoice.",
            "effect_class": "COMMUNICATION",
            "target_ref": "invoice://candidate/001",
            "internal_sandbox_only": False,
        }
    ]
    payload["agents"][0]["assigned_tool_ids"] = ["TOOL-INVOICE-SEND"]
    payload["agents"][1]["assigned_tool_ids"] = []
    receipt = engineer_coordination_plan(CoordinationEngineeringRequest.model_validate(payload))

    assert receipt["terminal_status"] == "BLOCKED"
    assert receipt["verification"]["first_blocker"] == "TOOL_AUTHORITY_REQUIRED:TOOL-INVOICE-SEND"
    assert receipt["tooling"][0]["disposition"] == "BLOCKED_PERMISSION"
    verifier = next(
        item
        for item in receipt["multi_agent_coordination"]["agents"]
        if item["agent_id"] == "AGT-VERIFIER"
    )
    assert verifier["disposition"] == "BLOCKED_DEPENDENCY"
    assert verifier["blocked_dependency_ids"] == ["AGT-DESIGNER"]
    assert receipt["alpha_plan"]["terminal_status"] == "BLOCKED"
    assert receipt["authority_granted"] is False
    assert receipt["external_actions_performed"] == 0


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (
            lambda payload: payload["tools"][0]["parameters"].update(
                {"api_key": "sk-example-not-a-real-key"}
            ),
            "forbidden authority or secret keys",
        ),
        (
            lambda payload: payload["agents"][0].update(
                {"depends_on_agent_ids": ["AGT-VERIFIER"]}
            ),
            "agent dependency graph contains a cycle",
        ),
        (
            lambda payload: payload["agents"][0].update(
                {"assigned_tool_ids": ["TOOL-NOT-REGISTERED"]}
            ),
            "references unknown tools",
        ),
    ],
)
def test_invalid_secret_cycle_and_reference_inputs_fail_closed(mutation, expected):
    payload = deepcopy(request_payload())
    mutation(payload)
    with pytest.raises(ValidationError, match=expected):
        CoordinationEngineeringRequest.model_validate(payload)


def test_state_values_affect_hash_but_are_not_echoed_in_receipt():
    payload = request_payload()
    first = engineer_coordination_plan(CoordinationEngineeringRequest.model_validate(payload))
    payload["state"]["values"]["verified_checks"] = 13
    second = engineer_coordination_plan(CoordinationEngineeringRequest.model_validate(payload))

    assert first["state"]["state_sha256"] != second["state"]["state_sha256"]
    assert "values" not in first["state"]


def test_last_available_iteration_emits_stop_without_running_a_loop():
    payload = request_payload()
    payload["iteration"]["current_iteration"] = 3
    receipt = engineer_coordination_plan(CoordinationEngineeringRequest.model_validate(payload))

    assert receipt["terminal_status"] == "BLOCKED"
    assert receipt["iteration"]["next_iteration"] is None
    assert receipt["verification"]["first_blocker"] == (
        "ITERATION_BUDGET_EXHAUSTED_AFTER_CURRENT_PASS"
    )


def test_parallel_agent_ceiling_partitions_an_independent_ready_set():
    payload = request_payload()
    payload["agents"] = [
        {
            "agent_id": f"AGT-WORKER-{index}",
            "role": "AUTO_ENGINEER",
            "mandate": f"Engineer bounded independent candidate number {index}.",
            "output_contract": "candidate receipt",
            "verification_function": "verification.run",
        }
        for index in range(1, 4)
    ]
    payload["coordination"]["maximum_parallel_agents"] = 2
    receipt = engineer_coordination_plan(CoordinationEngineeringRequest.model_validate(payload))

    assert receipt["multi_agent_coordination"]["waves"] == [
        {"wave": 0, "agent_ids": ["AGT-WORKER-1", "AGT-WORKER-2"]},
        {"wave": 1, "agent_ids": ["AGT-WORKER-3"]},
    ]


def test_indeterminate_tool_stops_at_read_only_reconciliation():
    payload = request_payload()
    payload["tools"] = [
        {
            "tool_id": "TOOL-OUTCOME-RECONCILE",
            "function_name": "external.outcome.reconcile",
            "purpose": "Represent an indeterminate prior external outcome.",
            "effect_class": "READ_EXTERNAL",
            "target_ref": "receipt://indeterminate/001",
            "outcome_indeterminate": True,
        }
    ]
    payload["agents"][0]["assigned_tool_ids"] = ["TOOL-OUTCOME-RECONCILE"]
    payload["agents"][1]["assigned_tool_ids"] = []
    receipt = engineer_coordination_plan(CoordinationEngineeringRequest.model_validate(payload))

    assert receipt["terminal_status"] == "BLOCKED"
    assert receipt["tooling"][0]["disposition"] == "RECONCILIATION_REQUIRED"
    assert receipt["verification"]["first_blocker"] == (
        "TOOL_RECONCILIATION_REQUIRED:TOOL-OUTCOME-RECONCILE"
    )
    reconciliation_node = next(
        node
        for node in receipt["alpha_plan"]["alpha_levels"][0]["nodes"]
        if node["name"] == "external.outcome.reconcile"
    )
    assert (
        reconciliation_node["authorization_requirements"]["authority_requirement"]
        == "RECONCILIATION"
    )
    assert receipt["alpha_plan"]["verification"]["first_blocker"].endswith(
        ":READ_ONLY_RECONCILIATION_REQUIRED"
    )
    assert receipt["external_actions_performed"] == 0


def test_oversized_nested_state_fails_the_global_request_ceiling():
    payload = request_payload()
    payload["state"]["values"] = {"oversized": "x" * 263_000}
    with pytest.raises(ValidationError, match="262144-byte contract ceiling"):
        CoordinationEngineeringRequest.model_validate(payload)
