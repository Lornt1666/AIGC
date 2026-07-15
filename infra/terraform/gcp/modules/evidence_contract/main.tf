locals {
  evidence_contract_safe = (
    var.repository_clean &&
    var.provider_lock_present &&
    var.resource_change_count == 0 &&
    var.hosted_ci_replacement == false &&
    var.operator_review_required == true &&
    var.provider_action_performed == false &&
    var.terraform_apply_performed == false &&
    var.external_action_performed == false
  )
}

check "repository_state_is_clean" {
  assert {
    condition     = var.repository_clean
    error_message = "The evidence contract requires a clean repository state."
  }
}

check "provider_lock_is_present" {
  assert {
    condition     = var.provider_lock_present
    error_message = "The committed Terraform provider lockfile is required."
  }
}

check "resource_graph_is_inert" {
  assert {
    condition     = var.resource_change_count == 0
    error_message = "The evidence-only Terraform plan must contain zero resource changes."
  }
}

check "local_evidence_does_not_replace_hosted_ci" {
  assert {
    condition     = var.hosted_ci_replacement == false
    error_message = "The evidence contract cannot replace hosted GitHub Actions evidence."
  }
}

check "operator_review_remains_required" {
  assert {
    condition     = var.operator_review_required
    error_message = "Operator review must remain required."
  }
}

check "no_provider_or_external_action" {
  assert {
    condition = (
      var.provider_action_performed == false &&
      var.terraform_apply_performed == false &&
      var.external_action_performed == false
    )
    error_message = "The evidence contract cannot report provider action, Terraform apply, or external action."
  }
}
