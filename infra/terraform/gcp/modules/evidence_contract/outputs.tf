output "evidence_contract" {
  description = "Provider-free evidence contract for plan and validation artifacts."
  value = {
    contract_id                  = "AIGC-TERRAFORM-INERT-EVIDENCE-CONTRACT-001"
    contract_version             = "1.0.0"
    source_revision              = var.source_revision
    expected_pr_number           = var.expected_pr_number
    branch_name                  = var.branch_name
    repository_clean             = var.repository_clean
    terraform_source_fingerprint = var.terraform_source_fingerprint
    provider_lock_present        = var.provider_lock_present
    provider_lock_sha256         = var.provider_lock_sha256
    resource_change_count        = var.resource_change_count
    evidence_contract_safe       = local.evidence_contract_safe
    hosted_ci_replacement        = var.hosted_ci_replacement
    operator_review_required     = var.operator_review_required
    provider_action_performed    = var.provider_action_performed
    terraform_apply_performed    = var.terraform_apply_performed
    external_action_performed    = var.external_action_performed
  }
}
