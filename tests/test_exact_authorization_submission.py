from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from src.core.exact_authorization_submission import (
    canonical_digest,
    evaluate_exact_authorization_submission,
    load_identifier_packet,
)


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40
NOW = datetime(2026, 7, 14, 12, 30, tzinfo=timezone.utc)


def validator(name: str) -> Draft202012Validator:
    schema = json.loads(
        (ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def staging_submission() -> dict[str, object]:
    packet = deepcopy(load_identifier_packet())
    packet.update(
        {
            "artifact_kind": "SUBMISSION",
            "packet_id": "EIP-" + "A" * 24,
            "staging_status": "READY_FOR_OPERATOR_REVIEW",
            "production_status": "AWAITING_IDENTIFIERS",
            "lifecycle": {
                "created_at": "2026-07-14T12:00:00+00:00",
                "expires_at": "2026-07-15T12:00:00+00:00",
                "supersedes_packet_id": None,
                "revoked": False,
                "revoked_at": None,
                "revocation_reason": None,
                "staging_consumption": {
                    "status": "UNUSED",
                    "consumed_at": None,
                    "consumed_by_receipt_id": None,
                },
                "production_consumption": {
                    "status": "UNUSED",
                    "consumed_at": None,
                    "consumed_by_receipt_id": None,
                },
            },
            "staging_identity": {
                "project_reference": "gcp_project://aigc-stage-123",
                "workload_identity_service_account_reference": (
                    "gcp_service_account://aigc-stage-123/"
                    "aigc-stage-runner@aigc-stage-123.iam.gserviceaccount.com"
                ),
                "session_pepper_secret_reference": (
                    "gcp_secret://aigc-stage-123/aigc-session-pepper/7"
                ),
                "test_subject_reference": "staging_subject://operator-test-001",
                "authorized_origins": ["https://stage.aigc.example"],
                "authorized_redirect_uris": [
                    "https://stage.aigc.example/auth/callback"
                ],
            },
            "unresolved_staging_identifiers": [],
        }
    )
    return packet


def full_submission() -> dict[str, object]:
    packet = staging_submission()
    packet["production_status"] = "READY_FOR_OPERATOR_REVIEW"
    packet["production_deployment"] = {
        "project_reference": "gcp_project://aigc-prod-123",
        "deployment_workload_identity_reference": (
            "gcp_service_account://aigc-prod-123/"
            "aigc-prod-runner@aigc-prod-123.iam.gserviceaccount.com"
        ),
        "release_id": "REL-AIGC-00000001",
        "release_candidate_digest": "b" * 64,
        "readiness_truth_digest": "c" * 64,
        "release_artifact_digest": "sha256:" + "d" * 64,
        "domain_reference": "dns_name://app.aigc.example",
        "database_reference": "cloud_sql://aigc-prod-123/aigc-postgres/aigc",
        "remote_state_reference": (
            "gcs_state://aigc-prod-123/aigc-tf-state/"
            "production/default.tfstate"
        ),
        "production_release_gate_receipt_id": "PRG-" + "E" * 24,
    }
    packet["unresolved_production_identifiers"] = []
    return packet


def staging_receipt(packet: dict[str, object]) -> dict[str, object]:
    return {
        "contract_id": "AIGC-STAGING-IDENTITY-AUTHORIZATION-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "SIA-APPROVAL-0001",
        "exact_revision": REVISION,
        "identifier_packet_digest": canonical_digest(packet),
        "decision": "APPROVED",
        "reason_codes": [],
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": "Justice Gray Maciocha",
        "issued_at": "2026-07-14T12:00:00+00:00",
        "expires_at": "2026-07-14T14:00:00+00:00",
        "environment": "isolated_staging",
        "targets": deepcopy(packet["staging_identity"]),
        "scope": {
            "staging_configuration_review_authorized": True,
            "identity_platform_configuration_authorized": True,
            "workload_identity_creation_authorized": True,
            "session_pepper_creation_authorized": True,
            "session_pepper_access_authorized": True,
            "test_subject_onboarding_authorized": True,
            "staging_sign_in_authorized": True,
        },
        "single_use": True,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "production_identity_activation_authorized": False,
        "production_deployment_authorized": False,
        "external_action_performed": False,
    }


def production_receipt(packet: dict[str, object]) -> dict[str, object]:
    production = packet["production_deployment"]
    return {
        "contract_id": "AIGC-PRODUCTION-DEPLOYMENT-AUTHORIZATION-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "PDA-APPROVAL-0001",
        "exact_revision": REVISION,
        "identifier_packet_digest": canonical_digest(packet),
        "decision": "APPROVED",
        "reason_codes": [],
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": "Justice Gray Maciocha",
        "issued_at": "2026-07-14T12:00:00+00:00",
        "expires_at": "2026-07-14T13:00:00+00:00",
        "release_id": production["release_id"],
        "release_candidate_digest": production["release_candidate_digest"],
        "readiness_truth_digest": production["readiness_truth_digest"],
        "release_artifact_digest": production["release_artifact_digest"],
        "production_project_reference": production["project_reference"],
        "deployment_workload_identity_reference": production[
            "deployment_workload_identity_reference"
        ],
        "domain_reference": production["domain_reference"],
        "database_reference": production["database_reference"],
        "remote_state_reference": production["remote_state_reference"],
        "production_release_gate_receipt_id": production[
            "production_release_gate_receipt_id"
        ],
        "production_release_gate_result": "PERMIT",
        "scope": {
            "production_identity_activation_authorized": True,
            "production_deployment_authorized": True,
        },
        "single_use": True,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "staging_identity_authorized": False,
        "external_action_performed": False,
    }


def readiness(score: float, ready: bool, blockers: list[str]) -> dict[str, object]:
    return {
        "source_revision": REVISION,
        "overall_score": score,
        "production_readiness_threshold": 90,
        "production_ready": ready,
        "blocking_gaps": blockers,
    }


def test_canonical_file_is_a_non_live_template() -> None:
    packet = load_identifier_packet()
    assert packet["artifact_kind"] == "TEMPLATE"
    assert packet["packet_id"] is None
    assert packet["staging_status"] == "AWAITING_IDENTIFIERS"
    assert packet["production_status"] == "AWAITING_IDENTIFIERS"

    result = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        now=NOW,
    ).receipt

    assert result["lifecycle_active"] is False
    assert "IDENTIFIER_PACKET_TEMPLATE_ONLY" in result["lifecycle_reason_codes"]
    assert result["staging_packet_ready_for_review"] is False
    assert result["production_packet_ready_for_review"] is False
    assert result["staging_identity_authorization_effective"] is False
    assert result["production_deployment_authorization_effective"] is False
    assert result["automatic_apply_allowed"] is False
    assert result["external_action_performed"] is False


def test_template_rejects_live_identifiers_and_manual_revision_binding() -> None:
    live_template = deepcopy(load_identifier_packet())
    live_template["staging_status"] = "READY_FOR_OPERATOR_REVIEW"
    live_template["staging_identity"]["project_reference"] = (
        "gcp_project://aigc-stage-123"
    )
    manually_bound = deepcopy(load_identifier_packet())
    manually_bound["authorization_basis_revision"] = REVISION

    packet_validator = validator("exact_identifier_submission_packet")
    assert list(packet_validator.iter_errors(live_template))
    assert list(packet_validator.iter_errors(manually_bound))


def test_staging_readiness_is_independent_from_production_readiness() -> None:
    packet = staging_submission()
    assert not list(
        validator("exact_identifier_submission_packet").iter_errors(packet)
    )

    result = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        now=NOW,
    ).receipt

    assert result["evaluated_revision"] == REVISION
    assert result["identifier_packet_digest"] == canonical_digest(packet)
    assert result["staging_packet_ready_for_review"] is True
    assert result["production_packet_ready_for_review"] is False
    assert result["staging_identity_authorization_effective"] is False
    assert result["production_deployment_authorization_effective"] is False


def test_staging_receipt_is_effective_only_for_exact_submission() -> None:
    packet = staging_submission()
    receipt = staging_receipt(packet)
    result = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        staging_identity_receipt=receipt,
        readiness_report=readiness(74.5, False, ["production_identity_access"]),
        now=NOW,
    ).receipt

    assert result["staging_identity_authorization_effective"] is True
    assert result["production_deployment_authorization_effective"] is False

    wrong = staging_receipt(packet)
    wrong["targets"]["project_reference"] = "gcp_project://wrong-stage-123"
    rejected = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        staging_identity_receipt=wrong,
        now=NOW,
    ).receipt
    assert rejected["staging_identity_authorization_effective"] is False
    assert "STAGING_IDENTITY_TARGET_MISMATCH" in rejected[
        "staging_identity_reason_codes"
    ]


def test_expired_or_revoked_submission_is_inactive() -> None:
    expired = staging_submission()
    expired["lifecycle"]["expires_at"] = "2026-07-14T12:15:00+00:00"
    expired_result = evaluate_exact_authorization_submission(
        identifier_packet=expired,
        exact_revision=REVISION,
        staging_identity_receipt=staging_receipt(expired),
        now=NOW,
    ).receipt
    assert expired_result["lifecycle_active"] is False
    assert "IDENTIFIER_PACKET_EXPIRED" in expired_result[
        "lifecycle_reason_codes"
    ]
    assert expired_result["staging_identity_authorization_effective"] is False

    revoked = staging_submission()
    revoked["lifecycle"]["revoked"] = True
    revoked["lifecycle"]["revoked_at"] = "2026-07-14T12:15:00+00:00"
    revoked["lifecycle"]["revocation_reason"] = "Operator withdrew submission."
    revoked_result = evaluate_exact_authorization_submission(
        identifier_packet=revoked,
        exact_revision=REVISION,
        staging_identity_receipt=staging_receipt(revoked),
        now=NOW,
    ).receipt
    assert "IDENTIFIER_PACKET_REVOKED" in revoked_result[
        "lifecycle_reason_codes"
    ]
    assert revoked_result["staging_identity_authorization_effective"] is False


def test_lane_consumption_is_independent() -> None:
    packet = full_submission()
    packet["lifecycle"]["staging_consumption"] = {
        "status": "CONSUMED",
        "consumed_at": "2026-07-14T12:20:00+00:00",
        "consumed_by_receipt_id": "SIA-APPROVAL-0001",
    }
    receipt = production_receipt(packet)
    result = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        production_deployment_receipt=receipt,
        readiness_report=readiness(95.0, True, []),
        now=NOW,
    ).receipt

    assert result["staging_packet_ready_for_review"] is False
    assert "STAGING_PACKET_ALREADY_CONSUMED" in result[
        "staging_identity_reason_codes"
    ]
    assert result["production_packet_ready_for_review"] is True
    assert result["production_deployment_authorization_effective"] is True


def test_symbolic_secret_and_invalid_consumption_are_rejected() -> None:
    symbolic = staging_submission()
    symbolic["staging_identity"]["session_pepper_secret_reference"] = (
        "gcp_secret://aigc-stage-123/aigc-session-pepper/latest"
    )
    invalid_consumption = staging_submission()
    invalid_consumption["lifecycle"]["staging_consumption"] = {
        "status": "CONSUMED",
        "consumed_at": None,
        "consumed_by_receipt_id": None,
    }

    packet_validator = validator("exact_identifier_submission_packet")
    assert list(packet_validator.iter_errors(symbolic))
    assert list(packet_validator.iter_errors(invalid_consumption))


def test_production_approval_remains_ineffective_at_current_readiness() -> None:
    packet = full_submission()
    receipt = production_receipt(packet)
    result = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        production_deployment_receipt=receipt,
        readiness_report=readiness(
            74.5,
            False,
            [
                "security_privacy_wiring",
                "transactional_persistence",
                "production_identity_access",
                "approved_external_connectors",
                "production_deployment",
            ],
        ),
        now=NOW,
    ).receipt

    assert result["production_packet_ready_for_review"] is True
    assert result["production_deployment_authorization_effective"] is False
    assert "READINESS_SCORE_BELOW_THRESHOLD" in result[
        "production_deployment_reason_codes"
    ]
    assert "BLOCKING_GAPS_PRESENT" in result[
        "production_deployment_reason_codes"
    ]


def test_production_receipt_can_be_effective_only_with_green_truth() -> None:
    packet = full_submission()
    receipt = production_receipt(packet)
    result = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        production_deployment_receipt=receipt,
        readiness_report=readiness(95.0, True, []),
        now=NOW,
    ).receipt

    assert result["production_deployment_authorization_effective"] is True
    assert result["operator_review_required"] is True
    assert result["automatic_apply_allowed"] is False
    assert result["external_action_performed"] is False


def test_evaluator_does_not_mutate_inputs() -> None:
    packet = full_submission()
    stage = staging_receipt(packet)
    production = production_receipt(packet)
    snapshot = deepcopy((packet, stage, production))
    evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        staging_identity_receipt=stage,
        production_deployment_receipt=production,
        readiness_report=readiness(95.0, True, []),
        now=NOW,
    )
    assert (packet, stage, production) == snapshot
