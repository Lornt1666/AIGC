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

module "cloud_sql_staging" {
  source = "./modules/cloud_sql"
  count = (
    local.resource_creation_effective &&
    var.environment == "staging" &&
    var.cloud_sql_enabled
  ) ? 1 : 0

  project_id                    = var.project_id
  region                        = var.primary_region
  instance_name                 = var.cloud_sql_instance_name
  network_name                  = var.cloud_sql_network_name
  private_service_range_name    = var.cloud_sql_private_service_range_name
  private_service_prefix_length = var.cloud_sql_private_service_prefix_length
  database_version              = var.cloud_sql_database_version
  edition                       = var.cloud_sql_edition
  tier                          = var.cloud_sql_tier
  availability_type             = var.cloud_sql_availability_type
  disk_type                     = var.cloud_sql_disk_type
  disk_size_gb                  = var.cloud_sql_disk_size_gb
  deletion_protection           = var.cloud_sql_deletion_protection
  database_name                 = var.cloud_sql_database_name
  backup_start_time             = var.cloud_sql_backup_start_time
  backup_retention_count        = var.cloud_sql_backup_retention_count
  transaction_log_retention_days = (
    var.cloud_sql_transaction_log_retention_days
  )
  ssl_mode                      = var.cloud_sql_ssl_mode
  maintenance_day               = var.cloud_sql_maintenance_day
  maintenance_hour              = var.cloud_sql_maintenance_hour
  query_insights_enabled        = var.cloud_sql_query_insights_enabled
  runtime_service_account_email = var.cloud_sql_runtime_service_account_email
  database_flags                = var.cloud_sql_database_flags
  labels = merge(
    var.cloud_sql_labels,
    {
      aigc_revision = substr(var.exact_revision, 0, 12)
    },
  )
}

# All resource-bearing modules must remain gated by
# local.resource_creation_effective and an explicit subsystem enable flag.
# Defining the module does not authorize Terraform plan or apply.
