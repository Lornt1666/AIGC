locals {
  exact_revision_bound = can(regex("^[a-f0-9]{40}$", var.exact_revision))
  image_digest_bound   = can(regex("^sha256:[a-f0-9]{64}$", var.image_digest))
  project_bound        = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
  domain_bound         = var.environment == "staging" || length(trimspace(var.production_domain)) > 0

  production_gate_bound = can(regex("^PRG-[A-F0-9]{24}$", var.release_gate_receipt_id))
  production_release_permitted = (
    var.environment == "production" &&
    var.release_gate_result == "PERMIT" &&
    var.deployment_authorized &&
    local.exact_revision_bound &&
    local.image_digest_bound &&
    local.project_bound &&
    local.domain_bound &&
    local.production_gate_bound
  )

  staging_plan_authorization_supplied = (
    var.staging_plan_authorization_path != "" ?
    fileexists(var.staging_plan_authorization_path) :
    false
  )
  staging_plan_authorization = (
    local.staging_plan_authorization_supplied ?
    try(jsondecode(file(var.staging_plan_authorization_path)), null) :
    null
  )
  staging_plan_gate_bound = try(
    local.staging_plan_authorization.contract_id == "AIGC-STAGING-INFRASTRUCTURE-PLAN-AUTHORIZATION-001" &&
    local.staging_plan_authorization.contract_version == "1.0.0" &&
    can(regex("^SIP-[A-F0-9]{24}$", local.staging_plan_authorization.receipt_id)) &&
    local.staging_plan_authorization.decision == "APPROVED" &&
    local.staging_plan_authorization.environment == "isolated_staging" &&
    local.staging_plan_authorization.exact_revision == var.exact_revision &&
    local.staging_plan_authorization.project_id == var.project_id &&
    local.staging_plan_authorization.terraform_root == "infra/terraform/gcp" &&
    local.staging_plan_authorization.terraform_fingerprint == var.staging_terraform_fingerprint &&
    can(regex("^[a-f0-9]{64}$", var.staging_terraform_fingerprint)) &&
    local.staging_plan_authorization.component == "cloud_sql" &&
    local.staging_plan_authorization.monthly_budget_cad > 0 &&
    local.staging_plan_authorization.monthly_budget_cad <= 50 &&
    local.staging_plan_authorization.resource_creation_authorized == true &&
    local.staging_plan_authorization.cloud_sql_enabled == true &&
    local.staging_plan_authorization.terraform_plan_authorized == true &&
    local.staging_plan_authorization.terraform_apply_authorized == false &&
    local.staging_plan_authorization.provider_mutation_authorized == false &&
    local.staging_plan_authorization.production_deployment_authorized == false &&
    local.staging_plan_authorization.production_data_allowed == false &&
    local.staging_plan_authorization.operator_review_required == true &&
    local.staging_plan_authorization.automatic_apply_allowed == false &&
    local.staging_plan_authorization.external_action_performed == false &&
    timecmp(local.staging_plan_authorization.issued_at, local.staging_plan_authorization.expires_at) < 0 &&
    timecmp(local.staging_plan_authorization.issued_at, plantimestamp()) <= 0 &&
    timecmp(plantimestamp(), local.staging_plan_authorization.expires_at) < 0,
    false,
  )
  staging_plan_permitted = (
    var.environment == "staging" &&
    local.exact_revision_bound &&
    local.project_bound &&
    local.staging_plan_gate_bound
  )

  release_permitted = (
    var.environment == "staging" ?
    local.staging_plan_permitted :
    local.production_release_permitted
  )
  gate_bound = (
    var.environment == "staging" ?
    local.staging_plan_gate_bound :
    local.production_gate_bound
  )
  authorization_mode = (
    var.environment == "staging" ?
    "staging_infrastructure_plan_authorization" :
    "production_release_gate"
  )

  resource_creation_effective = var.resource_creation_authorized && local.release_permitted
}

check "resource_creation_requires_environment_authority" {
  assert {
    condition     = !var.resource_creation_authorized || local.release_permitted
    error_message = "Resource definition requires exact revision and project binding plus a current staging plan authorization or production release permit, according to environment."
  }
}

check "staging_resource_definition_requires_plan_authorization" {
  assert {
    condition = (
      var.environment != "staging" ||
      !var.resource_creation_authorized ||
      local.staging_plan_permitted
    )
    error_message = "Staging resource definition requires an unexpired, exact-revision Cloud SQL plan-authorization receipt."
  }
}

check "production_resource_creation_requires_release_permit" {
  assert {
    condition = (
      var.environment != "production" ||
      !var.resource_creation_authorized ||
      local.production_release_permitted
    )
    error_message = "Production resource creation requires an exact revision, immutable image digest, candidate-bound production release-gate PERMIT, and deployment authorization."
  }
}

check "accepted_regions_are_fixed" {
  assert {
    condition = (
      var.primary_region == "northamerica-northeast2" &&
      var.recovery_region == "northamerica-northeast1"
    )
    error_message = "Regions must match the accepted Toronto primary and Montreal recovery decision."
  }
}

check "production_domain_required" {
  assert {
    condition     = var.environment != "production" || length(trimspace(var.production_domain)) > 0
    error_message = "A production domain is required before a production plan can be authorized."
  }
}
