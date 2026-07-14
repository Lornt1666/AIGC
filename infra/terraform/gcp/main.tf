provider "google" {
  project = var.project_id != "" ? var.project_id : null
  region  = var.primary_region
}

locals {
  topology = {
    runtime                    = "cloud_run_v2"
    ingress                    = "external_https_load_balancer_only"
    database                   = "cloud_sql_postgresql"
    secrets                    = "google_secret_manager"
    primary_region             = var.primary_region
    recovery_region            = var.recovery_region
    private_database_network   = true
    managed_tls                = true
    cloud_armor_required       = true
    canary_initial_percent     = 5
    canary_observation_minutes = 30
    monthly_budget_cad         = var.monthly_budget_cad
  }

  unresolved_inputs = compact([
    var.project_id == "" ? "project_id" : "",
    var.exact_revision == "" ? "exact_revision" : "",
    var.image_digest == "" ? "image_digest" : "",
    var.release_gate_receipt_id == "" ? "release_gate_receipt_id" : "",
    var.environment == "production" && var.production_domain == "" ? "production_domain" : "",
  ])
}

# This baseline intentionally creates no Google Cloud resources. Later reviewed
# modules must use local.resource_creation_effective as their count/for_each
# gate and must not bypass the release-gate checks in guardrails.tf.
