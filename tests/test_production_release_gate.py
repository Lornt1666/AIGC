from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from src.core.contract_validator import ContractValidationError, validate_artifact
from src.core.production_readiness_ledger import build_report, load_ledger
from src.core.production_release_gate import (
    evaluate_release_manifest,
    readiness_truth_digest,
    release_candidate_digest,
    write_gate_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40
NOW = datetime(2026, 7, 14, 1, 0, tzinfo=timezone.utc)


def policy() -> dict[str, object]:
    return json.loads(
        (ROOT / "config" / "production_release_gate.json").read_text(
            encoding="utf-8"
        )
    )


def evidence_receipts() -> dict[str, list[str]]:
    return {
        "ci": ["CI-EXACT-HEAD-001"],
        "security": ["SECURITY-REVIEW-001"],
        "privacy": ["PRIVACY-REVIEW-001"],
        "database_restore": ["DATABASE-RESTORE-001"],
        "rollback": ["ROLLBACK-DRILL-001"],
        "monitoring": ["MONITORING-RECEIPT-001"],
        "incident_response": ["INCIDENT-DRILL-001"],
    }


def ready_report(revision: str = REVISION) -> dict[str, object]:
    return {
        "ledger_id": "AIGC-PRODUCTION-READINESS-LEDGER-001",
        "source_revision": revision,
        "overall_score": 100.0,
        "production_readiness_threshold": 90.0,
        "production_ready": True,
        "blocking_gaps": [],
        "capability_results": [
            {
                "capability_id": "production_identity_access",
                "effective_status": "complete",
                "evidence_complete": True,
                "blocking_for_production": True,
                "missing_evidence": [],
            },
            {
                "capability_id": "production_deployment",
                "effective_status": "complete",
                "evidence_complete": True,
                "blocking_for_production": True,
                "missing_evidence": [],
            },
        ],
    }


def manifest(
    report: dict[str, object],
    *,
    exact_revision: str = REVISION,
    operator_decision: str = "APPROVED",
    created_at: datetime = NOW,
    expires_at: datetime | None = None,
) -> dict[str, object]:
    expiry = expires_at or (created_at + timedelta(hours=12))
    value: dict[str, object] = {
        "contract_id": "AIGC-PRODUCTION-RELEASE-MANIFEST-001",
        "contract_version": "1.0.0",
        "release_id": "REL-TEST-0001",
        "environment": "production",
        "exact_revision": exact_revision,
        "readiness_truth_digest": readiness_truth_digest(report),
        "expected_blocking_gaps": [],
        "release_artifact": {
            "kind": "container_image",
            "reference": "registry.example.invalid/aigc@sha256:" + "b" * 64,
            "digest": "sha256:" + "b" * 64,
            "immutable": True,
        },
        "evidence_receipts": evidence_receipts(),
        "created_at": created_at.isoformat(),
        "expires_at": expiry.isoformat(),
        "external_action_performed": False,
    }
    approved = operator_decision == "APPROVED"
    value["operator_approval"] = {
        "contract_id": "AIGC-PRODUCTION-RELEASE-OPERATOR-APPROVAL-001",
        "contract_version": "1.0.0",
        "receipt_id": "OPR-RELEASE:ABC12345",
        "release_id": value["release_id"],
        "exact_revision": exact_revision,
        "release_candidate_digest": release_candidate_digest(value),
        "decision": operator_decision,
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Reviewed the exact release candidate and evidence packet.",
        "issued_at": (created_at + timedelta(minutes=5)).isoformat(),
        "expires_at": (expiry - timedelta(minutes=5)).isoformat(),
        "production_deployment_authorized": approved,
        "external_action_performed": False,
    }
    return value


def test_release_contracts_and_policy_are_strict() -> None:
    report = ready_report()
    value = manifest(report)
    validate_artifact("production_release_gate_policy", policy())
    validate_artifact("production_release_operator_approval", value["operator_approval"])
    validate_artifact("production_release_manifest", value)

    injected = manifest(report)
    injected["claimed_readiness_score"] = 100
    with pytest.raises(ContractValidationError):
        validate_artifact("production_release_manifest", injected)


def test_fully_evidenced_ready_release_can_receive_permit() -> None:
    report = ready_report()
    evaluation = evaluate_release_manifest(
        project_root=ROOT,
        manifest=manifest(report),
        policy=policy(),
        readiness_report=report,
        actual_revision=REVISION,
        evaluated_at=NOW + timedelta(hours=1),
    )

    assert evaluation.permitted is True
    assert evaluation.receipt["result"] == "PERMIT"
    assert evaluation.receipt["reason_codes"] == []
    assert evaluation.receipt["deployment_authorized"] is True
    assert evaluation.receipt["release_candidate_digest"]
    assert evaluation.receipt["external_action_performed"] is False


def test_actual_repository_is_denied_even_with_complete_release_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_SHA", REVISION)
    report = build_report(
        ROOT,
        load_ledger(ROOT / "config" / "production_readiness_ledger.json"),
    )
    evaluation = evaluate_release_manifest(
        project_root=ROOT,
        manifest=manifest(report),
        policy=policy(),
        readiness_report=report,
        actual_revision=REVISION,
        evaluated_at=NOW + timedelta(hours=1),
    )

    assert evaluation.permitted is False
    assert evaluation.receipt["deployment_authorized"] is False
    assert "READINESS_SCORE_BELOW_THRESHOLD" in evaluation.receipt["reason_codes"]
    assert "BLOCKING_GAPS_PRESENT" in evaluation.receipt["reason_codes"]
    assert "READINESS_NOT_PRODUCTION_READY" in evaluation.receipt["reason_codes"]
    assert evaluation.receipt["actual_blocking_gaps"]


def test_operator_denial_is_mandatory_gate_failure() -> None:
    report = ready_report()
    evaluation = evaluate_release_manifest(
        project_root=ROOT,
        manifest=manifest(report, operator_decision="DENIED"),
        policy=policy(),
        readiness_report=report,
        actual_revision=REVISION,
        evaluated_at=NOW + timedelta(hours=1),
    )

    assert evaluation.permitted is False
    assert "OPERATOR_DENIED_RELEASE" in evaluation.receipt["reason_codes"]


def test_operator_approval_is_bound_to_candidate_digest() -> None:
    report = ready_report()
    changed = manifest(report)
    changed["operator_approval"]["release_candidate_digest"] = "d" * 64
    evaluation = evaluate_release_manifest(
        project_root=ROOT,
        manifest=changed,
        policy=policy(),
        readiness_report=report,
        actual_revision=REVISION,
        evaluated_at=NOW + timedelta(hours=1),
    )

    assert evaluation.permitted is False
    assert "OPERATOR_APPROVAL_CANDIDATE_MISMATCH" in evaluation.receipt["reason_codes"]


def test_revision_and_readiness_digest_are_bound() -> None:
    report = ready_report()
    changed = manifest(report, exact_revision="c" * 40)
    changed["readiness_truth_digest"] = "d" * 64
    evaluation = evaluate_release_manifest(
        project_root=ROOT,
        manifest=changed,
        policy=policy(),
        readiness_report=report,
        actual_revision=REVISION,
        evaluated_at=NOW + timedelta(hours=1),
    )

    assert evaluation.permitted is False
    assert "REVISION_MISMATCH" in evaluation.receipt["reason_codes"]
    assert "READINESS_DIGEST_MISMATCH" in evaluation.receipt["reason_codes"]


def test_expired_or_overlong_manifest_is_denied() -> None:
    report = ready_report()
    evaluation = evaluate_release_manifest(
        project_root=ROOT,
        manifest=manifest(
            report,
            created_at=NOW - timedelta(hours=30),
            expires_at=NOW - timedelta(hours=1),
        ),
        policy=policy(),
        readiness_report=report,
        actual_revision=REVISION,
        evaluated_at=NOW,
    )

    assert evaluation.permitted is False
    assert "MANIFEST_EXPIRED" in evaluation.receipt["reason_codes"]
    assert "MANIFEST_TTL_EXCEEDED" in evaluation.receipt["reason_codes"]
    assert "OPERATOR_APPROVAL_EXPIRED" in evaluation.receipt["reason_codes"]


def test_gate_receipt_can_be_written_without_deployment(tmp_path: Path) -> None:
    report = ready_report()
    evaluation = evaluate_release_manifest(
        project_root=ROOT,
        manifest=manifest(report),
        policy=policy(),
        readiness_report=report,
        actual_revision=REVISION,
        evaluated_at=NOW + timedelta(hours=1),
    )
    path = write_gate_receipt(
        ROOT,
        evaluation,
        artifact_root=tmp_path,
    )
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert stored == evaluation.receipt
    assert stored["external_action_performed"] is False
