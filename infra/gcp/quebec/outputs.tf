output "authority_state" {
  value = {
    resource_creation_authorized         = var.resource_creation_authorized
    staging_deployment_authorized        = var.staging_deployment_authorized
    production_activation_authorized     = false
    public_access_authorized             = false
    live_model_call_authorized           = false
    cross_region_replication_authorized  = false
    service_account_key_creation_allowed = false
    codex_cloud_region_verified_canada   = false
  }
}

output "regional_foundation" {
  value = local.create_resources ? {
    project_id                   = var.project_id
    project_number               = var.project_number
    region                       = var.region
    release_sha                  = var.release_sha
    release_tree_sha             = var.release_tree_sha
    resource_manifest_hash       = var.resource_manifest_sha256
    authorization_inventory_hash = var.authorization_inventory_sha256
    artifact_repository          = google_artifact_registry_repository.runtime[0].id
    cloud_sql_instance           = google_sql_database_instance.control[0].connection_name
    evidence_bucket              = google_storage_bucket.regional["evidence"].url
    judge_bucket                 = google_storage_bucket.regional["judge"].url
    receipt_bucket               = google_storage_bucket.regional["receipts"].url
    log_bucket                   = google_logging_project_bucket_config.regional[0].id
    key_ring                     = google_kms_key_ring.main[0].id
    canary_authority_key_version = google_kms_crypto_key_version.canary_authority_v1[0].id
    canary_authority_algorithm   = google_kms_crypto_key_version.canary_authority_v1[0].algorithm
    service_accounts             = { for key, account in google_service_account.identity : key => account.email }
  } : null
}

output "deployment_boundary" {
  value = {
    cloud_run_services_created_by_this_root  = false
    deployment_procedure                     = "exact authorization/CI-receipt governed immutable-digest private no-traffic deployment"
    live_model_call_requires_separate_permit = true
  }
}
