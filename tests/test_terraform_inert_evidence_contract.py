from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GCP_ROOT = ROOT / "infra" / "terraform" / "gcp"
MODULE_ROOT = GCP_ROOT / "modules" / "evidence_contract"
EVIDENCE_ROOT = GCP_ROOT / "evidence_only"
WORKFLOW = ROOT / ".github" / "workflows" / "aigc-ci.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def module_terraform() -> str:
    return "\n".join(read(path) for path in sorted(MODULE_ROOT.glob("*.tf")))


def evidence_terraform() -> str:
    return "\n".join(read(path) for path in sorted(EVIDENCE_ROOT.glob("*.tf")))


def test_evidence_contract_contains_no_provider_or_resource_surface() -> None:
    terraform = module_terraform() + "\n" + evidence_terraform()

    assert 'resource "' not in terraform
    assert 'data "' not in terraform
    assert 'provider "' not in terraform
    assert "terraform apply" not in terraform
    assert "secret_data" not in terraform
    assert "google_" not in terraform


def test_evidence_contract_enforces_inert_authority_flags() -> None:
    main = read(MODULE_ROOT / "main.tf")
    outputs = read(MODULE_ROOT / "outputs.tf")

    assert 'check "repository_state_is_clean"' in main
    assert 'check "provider_lock_is_present"' in main
    assert 'check "resource_graph_is_inert"' in main
    assert 'check "local_evidence_does_not_replace_hosted_ci"' in main
    assert 'check "operator_review_remains_required"' in main
    assert 'check "no_provider_or_external_action"' in main

    for field in (
        "hosted_ci_replacement",
        "operator_review_required",
        "provider_action_performed",
        "terraform_apply_performed",
        "external_action_performed",
        "resource_change_count",
        "evidence_contract_safe",
    ):
        assert field in outputs


def test_provider_free_root_fingerprints_canonical_sources_and_lockfile() -> None:
    main = read(EVIDENCE_ROOT / "main.tf")

    assert 'canonical_gcp_root = abspath("${path.root}/..")' in main
    assert 'fileset(local.canonical_gcp_root, "**/*.tf")' in main
    assert "filesha256" in main
    assert "terraform_source_fingerprint" in main
    assert 'provider_lock_path    = "${local.canonical_gcp_root}/.terraform.lock.hcl"' in main
    assert "provider_lock_present" in main
    assert "resource_change_count        = 0" in main
    assert "hosted_ci_replacement        = false" in main
    assert "terraform_apply_performed    = false" in main
    assert "external_action_performed    = false" in main


def test_evidence_example_is_inert_and_exact_revision_bound() -> None:
    example = read(EVIDENCE_ROOT / "evidence.tfvars.example")

    assert 'source_revision    = "0000000000000000000000000000000000000000"' in example
    assert "expected_pr_number = null" in example
    assert "repository_clean   = true" in example


def test_ci_validates_and_asserts_evidence_contract_output() -> None:
    workflow = read(WORKFLOW)

    assert "Validate provider-free Terraform evidence contract" in workflow
    assert 'evidence_root="infra/terraform/gcp/evidence_only"' in workflow
    assert "terraform -chdir=\"${evidence_root}\" fmt -check -recursive" in workflow
    assert "terraform -chdir=\"${evidence_root}\" init -backend=false -input=false" in workflow
    assert "terraform -chdir=\"${evidence_root}\" validate" in workflow
    assert "evidence-contract-plan.json" in workflow
    assert "evidence-contract-summary.json" in workflow
    assert "Provider-free evidence plan unexpectedly contains resource changes" in workflow
    assert '"contract_id": "AIGC-TERRAFORM-INERT-EVIDENCE-CONTRACT-001"' in workflow
    assert '"hosted_ci_replacement": False' in workflow
    assert '"terraform_apply_performed": False' in workflow
    assert '"external_action_performed": False' in workflow
    assert "terraform apply" not in workflow
