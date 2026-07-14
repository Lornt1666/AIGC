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


def resolved_packet() -> dict[str, object]:
    return {
        "contract_id": "AIGC-EXACT-IDENTIFIER-SUBMISSION-PACKET-001",
        "contract_version": "1.0.0",
        "packet_id": "EIP-" + "A" * 24,
        "status": "READY_FOR_OPERATOR_REVIEW",
        "authorization_basis_revision": REVISION,
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
        "production_deployment": {
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
            "database_reference": (
                "cloud_sql://aigc-prod-123/aigc-postgres/aigc"
            ),
            "remote_state_reference": (
                "gcs_state://aigc-prod-123/aigc-tf-state/production/default.tfstate"
            ),
            "production_release_gate_receipt_id": "PRG-" + "E" * 24,
        },
        "unresolved_identifiers": [],
        "raw_secret_values_present": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "external_action_performed": False,
    }


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


def test_canonical_packet_is_valid_and_remains_incomplete() -> None:
    packet = load_identifier_packet()
    assert packet["status"] == "AWAITING_IDENTIFIERS"
    result = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision="f5a264de374fe18b1db0090acaa8935ac55bb975",
        now=NOW,
    ).receipt

    assert result["packet_ready_for_review"] is False
    assert result["staging_identity_authorization_effective"] is False
    assert result["production_deployment_authorization_effective"] is False
    assert result["automatic_apply_allowed"] is False
    assert result["external_action_performed"] is False


def test_resolved_packet_validates_and_digest_is_deterministic() -> None:
    packet = resolved_packet()
    assert not list(validator("exact_identifier_submission_packet").iter_errors(packet))
    assert canonical_digest(packet) == canonical_digest(deepcopy(packet))


def test_ready_packet_rejects_missing_or_symbolic_identifiers() -> None:
    missing = resolved_packet()
    missing["staging_identity"]["project_reference"] = None
    symbolic = resolved_packet()
    symbolic["staging_identity"]["session_pepper_secret_reference"] = (
        "gcp_secret://aigc-stage-123/aigc-session-pepper/latest"
    )

    assert list(validator("exact_identifier_submission_packet").iter_errors(missing))
    assert list(validator("exact_identifier_submission_packet").iter_errors(symbolic))


def test_staging_receipt_is_effective_only_for_exact_packet_and_window() -> None:
    packet = resolved_packet()
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


def test_staging_receipt_rejects_future_expired_or_production_scope() -> None:
    packet = resolved_packet()
    future = staging_receipt(packet)
    future["issued_at"] = "2026-07-14T13:00:00+00:00"
    future["expires_at"] = "2026-07-14T14:00:00+00:00"
    result = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        staging_identity_receipt=future,
        now=NOW,
    ).receipt
    assert "STAGING_IDENTITY_RECEIPT_FUTURE_DATED" in result[
        "staging_identity_reason_codes"
    ]

    injected = staging_receipt(packet)
    injected["production_deployment_authorized"] = True
    rejected = evaluate_exact_authorization_submission(
        identifier_packet=packet,
        exact_revision=REVISION,
        staging_identity_receipt=injected,
        now=NOW,
    ).receipt
    assert rejected["staging_identity_authorization_effective"] is False
    assert "STAGING_IDENTITY_RECEIPT_INVALID" in rejected[
        "staging_identity_reason_codes"
    ]


def test_production_approval_remains_ineffective_at_current_readiness() -> None:
    packet = resolved_packet()
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

    assert result["production_deployment_authorization_effective"] is False
    assert "READINESS_SCORE_BELOW_THRESHOLD" in result[
        "production_deployment_reason_codes"
    ]
    assert "BLOCKING_GAPS_PRESENT" in result[
        "production_deployment_reason_codes"
    ]


def test_production_receipt_can_be_effective_only_with_green_release_truth() -> None:
    packet = resolved_packet()
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
    packet = resolved_packet()
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
