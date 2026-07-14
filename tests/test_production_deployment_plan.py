from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from src.core.production_deployment_plan import (
    evaluate_deployment_plan,
    load_deployment_policy,
    terraform_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "production_deployment_baseline.json"
SCHEMA = ROOT / "schemas" / "production_deployment_baseline.schema.json"
TERRAFORM = ROOT / "infra" / "terraform" / "gcp"
NOW = datetime(2026, 7, 14, 7, 0, tzinfo=timezone.utc)
REVISION = "a" * 40
IMAGE_DIGEST = "sha256:" + "b" * 64


def gate_receipt() -> dict[str, object]:
    return {
        "contract_id": "AIGC-PRODUCTION-RELEASE-GATE-RECEIPT-001",
        "contract_version": "1.0.0",
        "gate_receipt_id": "PRG-" + "A" * 24,
        "release_id": "REL-TEST0001",
        "exact_revision": REVISION,
        "result": "PERMIT",
        "reason_codes": [],
        "actual_readiness_score": 90.0,
        "required_readiness_score": 90.0,
        "actual_blocking_gaps": [],
        "manifest_digest": "c" * 64,
        "release_candidate_digest": "d" * 64,
        "readiness_truth_digest": "e" * 64,
        "release_artifact_digest": IMAGE_DIGEST,
        "operator_approval_receipt_id": "APPROVAL-TEST0001",
        "deployment_authorized": True,
        "evaluated_at": NOW.isoformat(),
        "external_action_performed": False,
    }


def staging_authorized_policy() -> dict[str, object]:
    policy = deepcopy(load_deployment_policy(CONFIG, SCHEMA))
    policy["authority"]["staging_resource_creation_authorized"] = True
    policy["authority"]["staging_apply_authorized"] = True
    return policy


def evaluate_staging(gate: dict[str, object]) -> object:
    return evaluate_deployment_plan(
        policy=staging_authorized_policy(),
        environment="staging",
        exact_revision=REVISION,
        project_id="aigc-staging-example",
        image_digest=IMAGE_DIGEST,
        release_gate_receipt=gate,
        production_domain=None,
        terraform_root=TERRAFORM,
        now=NOW,
    )


def test_real_deployment_policy_is_denied_and_creates_no_resources() -> None:
    policy = load_deployment_policy(CONFIG, SCHEMA)
    evaluation = evaluate_deployment_plan(
        policy=policy,
        environment="production",
        exact_revision=None,
        project_id=None,
        image_digest=None,
        release_gate_receipt=None,
        production_domain=None,
        terraform_root=TERRAFORM,
        now=NOW,
    )

    assert evaluation.plan_eligible is False
    assert set(evaluation.receipt["reason_codes"]) >= {
        "REVISION_UNBOUND",
        "PROJECT_ID_UNRESOLVED",
        "IMAGE_DIGEST_UNRESOLVED",
        "PRODUCTION_DOMAIN_UNRESOLVED",
        "RELEASE_GATE_RECEIPT_MISSING",
        "PRODUCTION_RESOURCE_CREATION_UNAUTHORIZED",
        "PRODUCTION_APPLY_UNAUTHORIZED",
        "PRODUCTION_DEPLOYMENT_UNAUTHORIZED",
        "DNS_CHANGE_UNAUTHORIZED",
    }
    assert evaluation.receipt["resource_creation_effective"] is False
    assert evaluation.receipt["external_action_performed"] is False


def test_synthetic_bound_candidate_can_be_plan_eligible_without_apply() -> None:
    evaluation = evaluate_staging(gate_receipt())

    assert evaluation.plan_eligible is True
    assert evaluation.receipt["result"] == "PLAN_ELIGIBLE"
    assert evaluation.receipt["reason_codes"] == []
    assert evaluation.receipt["resource_creation_effective"] is False
    assert evaluation.receipt["external_action_performed"] is False


def test_deployment_project_id_matches_secret_manager_boundary() -> None:
    maximum_project_id = "a" + ("b" * 28) + "1"
    for project_id in ("abc123", maximum_project_id):
        evaluation = evaluate_deployment_plan(
            policy=staging_authorized_policy(),
            environment="staging",
            exact_revision=REVISION,
            project_id=project_id,
            image_digest=IMAGE_DIGEST,
            release_gate_receipt=gate_receipt(),
            production_domain=None,
            terraform_root=TERRAFORM,
            now=NOW,
        )
        assert evaluation.plan_eligible is True
        assert "PROJECT_ID_UNRESOLVED" not in evaluation.receipt["reason_codes"]

    for project_id in (
        "short",
        "approved_project",
        "approved-project-",
        "a" * 31,
    ):
        evaluation = evaluate_deployment_plan(
            policy=staging_authorized_policy(),
            environment="staging",
            exact_revision=REVISION,
            project_id=project_id,
            image_digest=IMAGE_DIGEST,
            release_gate_receipt=gate_receipt(),
            production_domain=None,
            terraform_root=TERRAFORM,
            now=NOW,
        )
        assert evaluation.plan_eligible is False
        assert "PROJECT_ID_UNRESOLVED" in evaluation.receipt["reason_codes"]
        assert evaluation.receipt["resource_creation_effective"] is False


def test_gate_revision_and_artifact_are_candidate_bound() -> None:
    gate = gate_receipt()
    gate["exact_revision"] = "c" * 40
    gate["release_artifact_digest"] = "sha256:" + "d" * 64

    evaluation = evaluate_staging(gate)

    assert evaluation.plan_eligible is False
    assert "RELEASE_GATE_REVISION_MISMATCH" in evaluation.receipt["reason_codes"]
    assert "RELEASE_GATE_ARTIFACT_MISMATCH" in evaluation.receipt["reason_codes"]


def test_release_gate_receipt_must_satisfy_the_canonical_contract() -> None:
    incomplete_gate = {
        "gate_receipt_id": "PRG-" + "A" * 24,
        "result": "PERMIT",
        "deployment_authorized": True,
        "exact_revision": REVISION,
        "release_artifact_digest": IMAGE_DIGEST,
    }

    evaluation = evaluate_staging(incomplete_gate)

    assert evaluation.plan_eligible is False
    assert evaluation.receipt["reason_codes"] == ["RELEASE_GATE_RECEIPT_INVALID"]
    assert evaluation.receipt["release_gate_receipt_id"] is None
    assert evaluation.receipt["resource_creation_effective"] is False


def test_release_gate_receipt_rejects_unknown_fields_and_inconsistent_permit() -> None:
    unknown_field_gate = gate_receipt()
    unknown_field_gate["forged_authority"] = True
    unknown_field_evaluation = evaluate_staging(unknown_field_gate)

    inconsistent_permit_gate = gate_receipt()
    inconsistent_permit_gate["actual_blocking_gaps"] = ["production_deployment"]
    inconsistent_permit_evaluation = evaluate_staging(inconsistent_permit_gate)

    for evaluation in (unknown_field_evaluation, inconsistent_permit_evaluation):
        assert evaluation.plan_eligible is False
        assert evaluation.receipt["reason_codes"] == [
            "RELEASE_GATE_RECEIPT_INVALID"
        ]
        assert evaluation.receipt["release_gate_receipt_id"] is None
        assert evaluation.receipt["external_action_performed"] is False


def test_valid_denied_release_gate_cannot_enable_a_plan() -> None:
    denied_gate = gate_receipt()
    denied_gate["result"] = "DENY"
    denied_gate["reason_codes"] = ["BLOCKING_GAPS_PRESENT"]
    denied_gate["actual_blocking_gaps"] = ["production_deployment"]
    denied_gate["deployment_authorized"] = False
    denied_gate["operator_approval_receipt_id"] = None

    evaluation = evaluate_staging(denied_gate)

    assert evaluation.plan_eligible is False
    assert evaluation.receipt["reason_codes"] == ["RELEASE_GATE_DENIED"]
    assert evaluation.receipt["release_gate_receipt_id"] == denied_gate[
        "gate_receipt_id"
    ]


def test_terraform_baseline_contains_guards_and_no_google_resources() -> None:
    fingerprint = terraform_fingerprint(TERRAFORM)
    joined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(TERRAFORM.glob("*.tf"))
    )

    assert len(fingerprint) == 64
    assert "resource_creation_requires_release_permit" in joined
    assert 'release_gate_result == "PERMIT"' in joined
    assert "var.deployment_authorized" in joined
    assert "local.resource_creation_effective" in joined
    assert 'resource "google_' not in joined
