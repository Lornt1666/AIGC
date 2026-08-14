from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.alpha_plan.memory import SQLiteAlphaMemory
from src.alpha_plan.meta_policy import ShadowMetaLearner
from src.alpha_plan.models import AlphaOperationRequest, AlphaPlanRequest
from src.alpha_plan.orchestrator import compose_alpha_plan, load_alpha_plan_policy


ROOT = Path(__file__).resolve().parents[1]


def _request(*operations: AlphaOperationRequest) -> AlphaPlanRequest:
    return AlphaPlanRequest(
        request_id="ALPHA-REQ-TEST001",
        objective="Produce a deterministic, governed implementation plan.",
        context_refs=("artifact://requirements/example",),
        operations=operations,
        execution_requested=True,
    )


def test_default_alpha_plan_is_deterministic_hierarchical_and_zero_egress() -> None:
    request = _request()
    first = compose_alpha_plan(request)
    second = compose_alpha_plan(request)
    assert first == second
    assert first["terminal_status"] == "PASS"
    assert first["verification"]["simulation_result"] == "OK"
    assert [item["level"] for item in first["alpha_levels"]] == [0, 1]
    assert all(item["type"] == "atomic" for item in first["alpha_levels"][0]["nodes"])
    assert first["alpha_levels"][1]["nodes"][0]["type"] == "composite"
    assert first["provider_calls_performed"] == 0
    assert first["memory_writes_performed"] == 0
    assert first["policy_updates_applied"] == 0
    assert first["external_actions_performed"] == 0
    assert first["authority_granted"] is False
    assert len(first["receipt_sha256"]) == 64


def test_every_atomic_node_has_operational_metadata_and_stable_order() -> None:
    request = _request(
        AlphaOperationRequest(
            operation_id="ALPHA-OP-SECOND001",
            function_name="aigc.second",
            depends_on=("ALPHA-OP-FIRST001",),
            expected_outputs={"done": "boolean"},
            priority=20,
        ),
        AlphaOperationRequest(
            operation_id="ALPHA-OP-FIRST001",
            function_name="aigc.first",
            expected_outputs={"artifact": "object"},
            priority=10,
        ),
    )
    plan = compose_alpha_plan(request)
    assert [item["function"] for item in plan["execution_sequence"]] == [
        "aigc.first",
        "aigc.second",
    ]
    for node in plan["alpha_levels"][0]["nodes"]:
        assert node["preconditions"]
        assert node["postconditions"]
        assert len(node["idempotency_token"]) == 64
        assert node["authorization_requirements"]["authority_granted"] is False
        assert node["retry_policy"]["max_retries"] <= 2
        assert node["error_handling"]["indeterminate_result_policy"] == "STOP_AND_RECONCILE"
        assert node["observability"]["metrics"]
        assert "time_ms" in node["estimated_cost"]


def test_consequential_function_is_blocked_with_no_automatic_retry() -> None:
    plan = compose_alpha_plan(
        _request(
            AlphaOperationRequest(
                operation_id="ALPHA-OP-SEND001",
                function_name="calendar.create_event",
                parameters={"calendar_id": "calendar://operator", "title": "Kickoff"},
                expected_outputs={"event_receipt": "object"},
                effect_class="COMMUNICATION",
                target_ref="calendar://operator",
                communication=True,
            )
        )
    )
    node = plan["alpha_levels"][0]["nodes"][0]
    assert plan["terminal_status"] == "BLOCKED"
    assert plan["verification"]["simulation_result"] == "BLOCKED"
    assert node["disposition"] == "BLOCKED_PERMISSION"
    assert node["authorization_requirements"]["consent_required"] is True
    assert node["authorization_requirements"]["one_use_permit_required"] is True
    assert "EXACT_DESTINATION" in node["authorization_requirements"]["required_bindings"]
    assert node["retry_policy"]["strategy"] == "none"
    assert node["retry_policy"]["max_retries"] == 0
    assert plan["external_actions_performed"] == 0


@pytest.mark.parametrize(
    "parameters",
    [
        {"permit_id": "PERMIT-FAKE001"},
        {"nested": {"execution_authorized": True}},
        {"api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz123456"},
    ],
)
def test_operation_rejects_authority_and_secret_injection(parameters) -> None:
    with pytest.raises(ValidationError):
        AlphaOperationRequest(
            operation_id="ALPHA-OP-INJECT001",
            function_name="aigc.untrusted",
            parameters=parameters,
        )


def test_dependency_graph_rejects_unknown_and_cycles() -> None:
    with pytest.raises(ValueError, match="unknown dependencies"):
        compose_alpha_plan(
            _request(
                AlphaOperationRequest(
                    operation_id="ALPHA-OP-UNKNOWN001",
                    function_name="aigc.unknown",
                    depends_on=("ALPHA-OP-MISSING001",),
                )
            )
        )
    with pytest.raises(ValueError, match="contains a cycle"):
        compose_alpha_plan(
            _request(
                AlphaOperationRequest(
                    operation_id="ALPHA-OP-CYCLEA01",
                    function_name="aigc.cycle_a",
                    depends_on=("ALPHA-OP-CYCLEB01",),
                ),
                AlphaOperationRequest(
                    operation_id="ALPHA-OP-CYCLEB01",
                    function_name="aigc.cycle_b",
                    depends_on=("ALPHA-OP-CYCLEA01",),
                ),
            )
        )


def test_committed_json_schema_validates_the_canonical_plan() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "aigc_alpha_plan.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(compose_alpha_plan(_request()))


def test_sqlite_memory_requires_consent_enforces_ttl_and_rejects_secrets(tmp_path) -> None:
    memory = SQLiteAlphaMemory(tmp_path / "alpha-memory.sqlite3")
    with pytest.raises(PermissionError):
        memory.save_fact("prefs", {"tone": "concise"}, consent_artifact_ref="missing")
    fact_id = memory.save_fact(
        "prefs",
        {"tone": "concise"},
        consent_artifact_ref="consent://operator/prefs-v1",
        ttl_seconds=10,
        authoritative_epoch=100,
    )
    assert fact_id.startswith("ALPHA-FACT-")
    assert memory.get_fact("prefs", authoritative_epoch=109)["value"] == {"tone": "concise"}
    assert memory.get_fact("prefs", authoritative_epoch=110) is None
    with pytest.raises(ValueError, match="credential-like"):
        memory.save_fact(
            "secret",
            {"api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz123456"},
            consent_artifact_ref="consent://operator/unsafe",
        )
    memory.close()


def test_episode_memory_and_meta_learning_are_retained_but_shadow_only(tmp_path) -> None:
    memory = SQLiteAlphaMemory(tmp_path / "alpha-memory.sqlite3")
    episode_id = memory.append_episode(
        {"state": {"request_class": "LOCAL"}, "action": "default", "reward": 0.5},
        retention_seconds=100,
        authoritative_epoch=100,
    )
    assert episode_id.startswith("ALPHA-EPISODE-")
    episodes = memory.sample_meta_batch(authoritative_epoch=150)
    learner = ShadowMetaLearner(load_alpha_plan_policy().stable_meta_config)
    suggestion = learner.suggest_config({"request_class": "LOCAL"})
    proposal = learner.propose_update(episodes)
    assert suggestion["applied"] is False
    assert suggestion["exploration_enabled"] is False
    assert proposal["applied"] is False
    assert proposal["shadow_evaluation_required"] is True
    assert proposal["human_review_required"] is True
    assert len(proposal["proposal_sha256"]) == 64
    assert memory.purge_expired(authoritative_epoch=200) == 1
    memory.close()


def test_sqlite_memory_queries_and_deletes_with_consent(tmp_path) -> None:
    memory = SQLiteAlphaMemory(tmp_path / "alpha-memory.sqlite3")
    memory.save_fact(
        "prefs.theme",
        {"value": "dark"},
        consent_artifact_ref="consent://fact/test",
    )
    memory.save_fact(
        "prefs.locale",
        {"value": "en-CA"},
        consent_artifact_ref="consent://fact/test",
    )
    assert [item["key"] for item in memory.query_facts("prefs.")] == [
        "prefs.locale",
        "prefs.theme",
    ]
    with pytest.raises(PermissionError, match="consent"):
        memory.delete_fact(
            "prefs.theme", consent_artifact_ref="artifact://not-consent"
        )
    assert memory.delete_fact(
        "prefs.theme", consent_artifact_ref="consent://delete/test"
    )
    assert memory.get_fact("prefs.theme") is None
    memory.close()
