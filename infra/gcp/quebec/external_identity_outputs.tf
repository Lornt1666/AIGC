output "github_workload_identity" {
  value = local.create_resources ? {
    pool_name                    = google_iam_workload_identity_pool.github[0].name
    provider_name                = google_iam_workload_identity_pool_provider.github[0].name
    federated_service_account    = google_service_account.identity["security_review"].email
    mutating_deployer_federated  = false
    repository                   = local.github_repository
    repository_id                = local.github_repository_id
    repository_owner_id          = local.github_repository_owner_id
    service_account_keys_created = false
  } : null
}

output "regional_secret_metadata" {
  value = local.create_resources ? {
    for purpose, secret in google_secret_manager_regional_secret.runtime :
    purpose => {
      secret_id        = secret.secret_id
      location         = secret.location
      resource         = "projects/${var.project_id}/locations/${var.region}/secrets/${secret.secret_id}"
      contains_version = false
      contains_value   = false
    }
  } : null
}
