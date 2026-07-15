from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "infra" / "terraform" / "gcp"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_staging_gate_consumes_exact_authorization_receipt() -> None:
    guardrails = read(TERRAFORM / "guardrails.tf")
    variables = read(TERRAFORM / "staging_authorization_variables.tf")
    assert 'variable "staging_plan_authorization_path"' in variables
    assert 'variable "staging_terraform_fingerprint"' in variables
    assert "fileexists(var.staging_plan_authorization_path)" in guardrails
    assert "jsondecode(file(var.staging_plan_authorization_path))" in guardrails
    assert "AIGC-STAGING-INFRASTRUCTURE-PLAN-AUTHORIZATION-001" in guardrails
    assert 'local.staging_plan_authorization.exact_revision == var.exact_revision' in guardrails
    assert 'local.staging_plan_authorization.project_id == var.project_id' in guardrails
    assert "plantimestamp()" in guardrails
    assert "timecmp(" in guardrails


def test_staging_and_production_authority_are_separate() -> None:
    guardrails = read(TERRAFORM / "guardrails.tf")
    assert "local.staging_plan_permitted" in guardrails
    assert "local.production_release_permitted" in guardrails
    assert 'var.release_gate_result == "PERMIT"' in guardrails
    assert "production_resource_creation_requires_release_permit" in guardrails
    assert "staging_resource_definition_requires_plan_authorization" in guardrails


def test_committed_example_keeps_all_three_conditions_false() -> None:
    example = read(TERRAFORM / "staging.tfvars.example")
    assert 'environment = "staging"' in example
    assert 'staging_plan_authorization_path = ""' in example
    assert 'staging_terraform_fingerprint   = ""' in example
    assert "resource_creation_authorized = false" in example
    assert "cloud_sql_enabled            = false" in example
    assert 'release_gate_result     = "DENY"' in example


def test_plan_preparation_does_not_authorize_apply() -> None:
    script = read(ROOT / "scripts" / "prepare_staging_cloud_sql_plan.py")
    assert '"resource_creation_authorized": True' in script
    assert '"cloud_sql_enabled": True' in script
    assert '"deployment_authorized": False' in script
    assert '"terraform_apply_authorized": False' in script
    assert "terraform apply" not in script


def test_apply_wrapper_requires_explicit_execute_and_exact_saved_plan() -> None:
    script = read(ROOT / "scripts" / "apply_staging_cloud_sql_plan.py")
    assert '"--execute"' in script
    assert '"--plan-authorization"' in script
    assert "validate_apply_authorization" in script
    assert '[terraform, "apply", "-input=false", str(plan_path)]' in script
    assert "-auto-approve" not in script
    assert "if not args.execute" in script
    assert "VALIDATED_NOT_EXECUTED" in script


def test_authorization_builder_requires_explicit_decision() -> None:
    script = read(ROOT / "scripts" / "build_staging_infrastructure_authorization.py")
    assert 'choices=("APPROVED", "DENIED")' in script
    assert "APPROVED receipts cannot include reason codes" in script
    assert "DENIED receipts require at least one --reason" in script
    assert "Plan authorization TTL must be between 1 and 240 minutes" in script
    assert "Apply authorization TTL must be between 1 and 60 minutes" in script
