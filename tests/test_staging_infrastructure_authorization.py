from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.staging_infrastructure_authorization import (
    canonical_digest,
    file_digest,
    recursive_terraform_fingerprint,
    validate_apply_authorization,
    validate_plan_authorization,
)


REVISION = "a" * 40
PROJECT_ID = "aigc-staging-001"
NOW = datetime(2026, 7, 15, 13, 0, tzinfo=timezone.utc)


def terraform_root(tmp_path: Path) -> Path:
    root = tmp_path / "infra" / "terraform" / "gcp"
    module = root / "modules" / "cloud_sql"
    module.mkdir(parents=True)
    (root / "main.tf").write_text('module "cloud_sql" { source = "./modules/cloud_sql" }\n')
    (module / "main.tf").write_text('resource "google_sql_database" "app" { name = "aigc" }\n')
    return root


def discovery_evidence() -> dict[str, object]:
    return {
        "contract_id": "AIGC-PROVIDER-DISCOVERY-EVIDENCE-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "SDE-TESTDISCOVERY0001",
        "exact_revision": REVISION,
        "procurement_pack_digest": "b" * 64,
        "discovery_authorization_receipt_id": "SDA-TESTAUTHORIZATION01",
        "target_project_reference": f"gcp_project://{PROJECT_ID}",
        "collected_at": (NOW - timedelta(minutes=30)).isoformat(),
        "result": "SUCCESS",
        "review_status": "ACCEPTED",
        "observed_resources": [
            {
                "resource_type": "PROJECT",
                "target_reference": f"gcp_project://{PROJECT_ID}",
                "existence_status": "EXISTS",
                "evidence_digest": "c" * 64,
            }
        ],
        "enabled_api_service_names": [],
        "service_account_key_counts": [],
        "identity_platform_configuration_status": "UNKNOWN",
        "state_backend_status": "MISSING",
        "unresolved_requirements": [],
        "raw_secret_values_present": False,
        "mutation_performed": False,
        "secret_value_access_performed": False,
        "provider_read_performed": True,
        "external_action_performed": True,
    }


def plan_authorization(root: Path) -> dict[str, object]:
    discovery = discovery_evidence()
    return {
        "contract_id": "AIGC-STAGING-INFRASTRUCTURE-PLAN-AUTHORIZATION-001",
        "contract_version": "1.0.0",
        "receipt_id": "SIP-" + "A" * 24,
        "decision": "APPROVED",
        "reason_codes": [],
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": "Justice Gray Maciocha",
        "environment": "isolated_staging",
        "exact_revision": REVISION,
        "project_id": PROJECT_ID,
        "terraform_root": "infra/terraform/gcp",
        "terraform_fingerprint": recursive_terraform_fingerprint(root),
        "component": "cloud_sql",
        "monthly_budget_cad": 50,
        "provider_discovery_evidence_receipt_id": discovery["receipt_id"],
        "provider_discovery_evidence_digest": canonical_digest(discovery),
        "issued_at": (NOW - timedelta(minutes=10)).isoformat(),
        "expires_at": (NOW + timedelta(hours=2)).isoformat(),
        "resource_creation_authorized": True,
        "cloud_sql_enabled": True,
        "terraform_plan_authorized": True,
        "terraform_apply_authorized": False,
        "provider_mutation_authorized": False,
        "production_deployment_authorized": False,
        "production_data_allowed": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "external_action_performed": False,
    }


def apply_authorization(root: Path, plan_auth: dict[str, object], plan: Path) -> dict[str, object]:
    return {
        "contract_id": "AIGC-STAGING-INFRASTRUCTURE-APPLY-AUTHORIZATION-001",
        "contract_version": "1.0.0",
        "receipt_id": "SIA-" + "B" * 24,
        "decision": "APPROVED",
        "reason_codes": [],
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": "Justice Gray Maciocha",
        "environment": "isolated_staging",
        "exact_revision": REVISION,
        "project_id": PROJECT_ID,
        "terraform_root": "infra/terraform/gcp",
        "terraform_fingerprint": recursive_terraform_fingerprint(root),
        "component": "cloud_sql",
        "plan_authorization_receipt_id": plan_auth["receipt_id"],
        "plan_authorization_digest": canonical_digest(plan_auth),
        "saved_plan_digest": file_digest(plan),
        "issued_at": (NOW - timedelta(minutes=5)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=30)).isoformat(),
        "single_use": True,
        "provider_mutation_authorized": True,
        "terraform_apply_authorized": True,
        "production_deployment_authorized": False,
        "production_data_allowed": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }


def test_plan_authorization_becomes_effective_with_accepted_discovery(tmp_path: Path) -> None:
    root = terraform_root(tmp_path)
    evaluation = validate_plan_authorization(
        authorization=plan_authorization(root),
        discovery_evidence=discovery_evidence(),
        project_root=tmp_path,
        terraform_root=root,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )

    assert evaluation.effective is True
    assert evaluation.reason_codes == ()
    assert evaluation.project_id == PROJECT_ID


def test_plan_authorization_rejects_expiry_revision_and_terraform_drift(tmp_path: Path) -> None:
    root = terraform_root(tmp_path)
    authorization = plan_authorization(root)
    authorization["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
    authorization["exact_revision"] = "d" * 40
    (root / "drift.tf").write_text('output "drift" { value = true }\n')

    evaluation = validate_plan_authorization(
        authorization=authorization,
        discovery_evidence=discovery_evidence(),
        project_root=tmp_path,
        terraform_root=root,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )

    assert evaluation.effective is False
    assert set(evaluation.reason_codes) >= {
        "PLAN_REVISION_MISMATCH",
        "PLAN_TERRAFORM_FINGERPRINT_MISMATCH",
        "PLAN_AUTHORIZATION_EXPIRED",
    }


def test_plan_authorization_rejects_unaccepted_discovery(tmp_path: Path) -> None:
    root = terraform_root(tmp_path)
    discovery = discovery_evidence()
    authorization = plan_authorization(root)
    discovery["review_status"] = "REJECTED"
    authorization["provider_discovery_evidence_digest"] = canonical_digest(discovery)

    evaluation = validate_plan_authorization(
        authorization=authorization,
        discovery_evidence=discovery,
        project_root=tmp_path,
        terraform_root=root,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )

    assert evaluation.effective is False
    assert "PLAN_DISCOVERY_NOT_ACCEPTED" in evaluation.reason_codes


def test_fingerprint_ignores_downloaded_terraform_modules(tmp_path: Path) -> None:
    root = terraform_root(tmp_path)
    before = recursive_terraform_fingerprint(root)
    downloaded = root / ".terraform" / "modules" / "external"
    downloaded.mkdir(parents=True)
    (downloaded / "main.tf").write_text('output "downloaded" { value = true }\n')

    assert recursive_terraform_fingerprint(root) == before


def test_apply_authorization_binds_exact_saved_plan(tmp_path: Path) -> None:
    root = terraform_root(tmp_path)
    plan_auth = plan_authorization(root)
    saved_plan = tmp_path / "cloud-sql.tfplan"
    saved_plan.write_bytes(b"exact-plan-v1")
    authorization = apply_authorization(root, plan_auth, saved_plan)

    effective = validate_apply_authorization(
        authorization=authorization,
        plan_authorization=plan_auth,
        saved_plan_path=saved_plan,
        project_root=tmp_path,
        terraform_root=root,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )
    assert effective.effective is True

    saved_plan.write_bytes(b"altered-plan")
    rejected = validate_apply_authorization(
        authorization=authorization,
        plan_authorization=plan_auth,
        saved_plan_path=saved_plan,
        project_root=tmp_path,
        terraform_root=root,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )
    assert rejected.effective is False
    assert "APPLY_SAVED_PLAN_DIGEST_MISMATCH" in rejected.reason_codes


def test_apply_authorization_rejects_changed_plan_authority(tmp_path: Path) -> None:
    root = terraform_root(tmp_path)
    plan_auth = plan_authorization(root)
    saved_plan = tmp_path / "cloud-sql.tfplan"
    saved_plan.write_bytes(b"exact-plan-v1")
    authorization = apply_authorization(root, plan_auth, saved_plan)
    changed = deepcopy(plan_auth)
    changed["approved_by_name"] = "Different Operator"

    evaluation = validate_apply_authorization(
        authorization=authorization,
        plan_authorization=changed,
        saved_plan_path=saved_plan,
        project_root=tmp_path,
        terraform_root=root,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )

    assert evaluation.effective is False
    assert "APPLY_PLAN_AUTHORIZATION_DIGEST_MISMATCH" in evaluation.reason_codes
