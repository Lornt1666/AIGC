locals {
  exact_revision_bound = can(regex("^[a-f0-9]{40}$", var.exact_revision))
  image_digest_bound   = can(regex("^sha256:[a-f0-9]{64}$", var.image_digest))
  project_bound        = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
  domain_bound         = var.environment == "staging" || length(trimspace(var.production_domain)) > 0
  gate_bound           = can(regex("^PRG-[A-F0-9]{24}$", var.release_gate_receipt_id))

  release_permitted = (
    var.release_gate_result == "PERMIT" &&
    var.deployment_authorized &&
    local.exact_revision_bound &&
    local.image_digest_bound &&
    local.project_bound &&
    local.domain_bound &&
    local.gate_bound
  )

  resource_creation_effective = var.resource_creation_authorized && local.release_permitted
}

check "resource_creation_requires_release_permit" {
  assert {
    condition     = !var.resource_creation_authorized || local.release_permitted
    error_message = "Resource creation requires an exact revision, immutable image digest, project, domain where required, candidate-bound release-gate PERMIT, and deployment authorization."
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
