from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "aigc-canadian-cloud-operator"
SCRIPT_PATH = SKILL_ROOT / "scripts" / "validate_canadian_execution.py"
EXAMPLE_PATH = SKILL_ROOT / "assets" / "execution-contract.example.json"

spec = importlib.util.spec_from_file_location("canadian_execution_validator", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def staging_contract() -> dict:
    payload = example()
    payload.update(
        {
            "contract_id": "AIGC-CANADIAN-STAGING-TEST-001",
            "task_type": "canadian_staging_execution",
            "environment": "STAGING",
            "requested_branch": "feat/canadian-staging-test",
            "requested_sha": "a" * 40,
            "requested_tree_sha": "b" * 40,
        }
    )
    execution = payload["canadian_execution_plane"]
    execution["required"] = True
    for name in (
        "service_location_availability_reviewed",
        "region_lock_reviewed",
        "resource_inventory_complete",
        "logging_region_reviewed",
        "backup_region_reviewed",
        "evidence_region_reviewed",
        "secret_manager_exact_versions_reviewed",
    ):
        execution[name] = True
    privacy = payload["privacy"]
    privacy.update(
        {
            "cross_border_assessment_completed": True,
            "purpose_limitation_recorded": True,
            "data_minimization_reviewed": True,
            "retention_schedule_recorded": True,
        }
    )
    payload["spending"].update(
        {
            "authorized_ceiling": 50,
            "budget_and_quota_reviewed": True,
        }
    )
    payload["authorization"].update(
        {
            "human_approval_recorded": True,
            "staging_execution_authorized": True,
            "deployment_authorized": True,
            "authorized_by": "Accountable owner",
            "authorized_at": "2026-08-06T16:00:00Z",
            "expires_at": "2026-08-07T16:00:00Z",
        }
    )
    return payload


def test_repository_skill_has_required_metadata_and_no_laptop_boundary() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert skill.startswith("---\nname: aigc-canadian-cloud-operator\n")
    assert "description:" in skill.split("---", 2)[1]
    assert "local laptop" in skill.lower()
    assert "northamerica-northeast1" in skill
    assert "codex_cloud_region_verified_canada=false" in skill
    assert "production_activation_authorized=false" in skill


def test_default_deny_example_passes_plan_structure_only() -> None:
    result = validator.validate_contract(example(), gate="plan")

    assert result["valid"] is True
    assert result["ready_for_gate"] is True
    assert result["codex_local_laptop_required"] is False
    assert result["codex_cloud_region_verified_canada"] is False
    assert result["approved_region"] == "northamerica-northeast1"
    assert result["production_activation_authorized"] is False


def test_non_canadian_region_and_silent_failover_fail_closed() -> None:
    payload = example()
    payload["canadian_execution_plane"]["primary_region"] = "us-central1"
    with pytest.raises(validator.ContractError, match="approved Canadian"):
        validator.validate_contract(payload, gate="plan")

    payload = example()
    payload["canadian_execution_plane"]["silent_failover_allowed"] = True
    with pytest.raises(validator.ContractError, match="silent failover"):
        validator.validate_contract(payload, gate="plan")


def test_codex_region_cannot_be_self_declared_canadian() -> None:
    payload = example()
    payload["codex"]["cloud_region_verified_canada"] = True

    with pytest.raises(validator.ContractError, match="must not be represented"):
        validator.validate_contract(payload, gate="plan")


def test_raw_secret_bearing_contract_fields_are_rejected() -> None:
    payload = example()
    payload["api_key"] = "nonempty"

    with pytest.raises(validator.ContractError, match="raw secret-bearing field"):
        validator.validate_contract(payload, gate="plan")


def test_ci_gate_requires_exact_revision_and_never_deployment_authority() -> None:
    payload = example()
    payload.update(
        {
            "environment": "CI",
            "requested_branch": "feature/exact-head",
            "requested_sha": "a" * 40,
            "requested_tree_sha": "b" * 40,
        }
    )
    result = validator.validate_contract(payload, gate="ci")
    assert result["ready_for_gate"] is True

    payload["authorization"]["deployment_authorized"] = True
    with pytest.raises(validator.ContractError, match="must not authorize deployment"):
        validator.validate_contract(payload, gate="ci")


def test_staging_gate_accepts_only_complete_no_production_packet() -> None:
    result = validator.validate_contract(
        staging_contract(),
        gate="staging",
        now=datetime(2026, 8, 6, 17, tzinfo=timezone.utc),
    )

    assert result["ready_for_gate"] is True
    assert result["canadian_execution_plane_required"] is True
    assert result["approved_region_label"] == "Montréal, Quebec, Canada"
    assert result["live_model_call_authorized"] is False
    assert result["merge_authorized"] is False


def test_personal_runtime_data_requires_completed_pia() -> None:
    payload = staging_contract()
    payload["privacy"]["canadian_runtime_contains_personal_information"] = True

    with pytest.raises(validator.ContractError, match="requires a PIA"):
        validator.validate_contract(
            payload,
            gate="staging",
            now=datetime(2026, 8, 6, 17, tzinfo=timezone.utc),
        )

    payload["privacy"].update(
        {
            "privacy_impact_assessment_required": True,
            "privacy_impact_assessment_completed": True,
        }
    )
    result = validator.validate_contract(
        payload,
        gate="staging",
        now=datetime(2026, 8, 6, 17, tzinfo=timezone.utc),
    )
    assert result["runtime_personal_information"] is True


def test_production_live_send_merge_and_financial_authority_remain_false() -> None:
    for field in validator.ALWAYS_FALSE_AUTHORITIES:
        payload = deepcopy(staging_contract())
        payload["authorization"][field] = True
        with pytest.raises(validator.ContractError, match=field):
            validator.validate_contract(
                payload,
                gate="staging",
                now=datetime(2026, 8, 6, 17, tzinfo=timezone.utc),
            )
