locals {
  github_repository          = "Lornt1666/AIGC"
  github_repository_id       = "1287333065"
  github_repository_owner_id = "236225491"
  github_wif_pool_id         = "${var.resource_prefix}-gha"
  github_wif_provider_id     = "github"

  regional_secret_ids = {
    runtime_control_dsn       = "${var.resource_prefix}-runtime-control-dsn"
    operator_token            = "${var.resource_prefix}-operator-token"
    operator_binding_key      = "${var.resource_prefix}-operator-binding-key"
    runtime_admin_token       = "${var.resource_prefix}-runtime-admin-token"
    runtime_admin_binding_key = "${var.resource_prefix}-runtime-admin-binding-key"
    judge_token               = "${var.resource_prefix}-judge-token"
    judge_binding_key         = "${var.resource_prefix}-judge-binding-key"
    openai_api_key            = "${var.resource_prefix}-openai-api-key"
  }

  operator_secret_purposes = toset([
    "runtime_control_dsn",
    "operator_token",
    "operator_binding_key",
    "runtime_admin_token",
    "runtime_admin_binding_key",
    "openai_api_key",
  ])
  judge_secret_purposes = toset(["judge_token", "judge_binding_key"])
}

resource "google_iam_workload_identity_pool" "github" {
  count = local.create_resources ? 1 : 0

  project                   = var.project_id
  workload_identity_pool_id = local.github_wif_pool_id
  display_name              = "AIGC GitHub staging"
  description               = "Keyless GitHub Actions identity for the governed AIGC release train."
  disabled                  = false

  depends_on = [google_project_service.platform_control_plane]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count = local.create_resources ? 1 : 0

  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = local.github_wif_provider_id
  display_name                       = "AIGC GitHub OIDC"
  description                        = "Repository-ID and owner-ID restricted GitHub OIDC provider."

  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository"          = "assertion.repository"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
    "attribute.ref"                 = "assertion.ref"
    "attribute.workflow_ref"        = "assertion.job_workflow_ref"
  }

  attribute_condition = join(" && ", [
    "assertion.repository == '${local.github_repository}'",
    "assertion.repository_id == '${local.github_repository_id}'",
    "assertion.repository_owner_id == '${local.github_repository_owner_id}'",
    "assertion.ref_type == 'branch'",
    "(assertion.ref == 'refs/heads/release/aigc-nexus-v1' || assertion.ref == 'refs/heads/main')",
  ])

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif_deployer" {
  count = local.create_resources ? 1 : 0

  service_account_id = google_service_account.identity["deployer"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github[0].workload_identity_pool_id}/attribute.repository_id/${local.github_repository_id}"
}

resource "google_project_iam_member" "deployer_cloud_build" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.identity["deployer"].email}"
}

resource "google_service_account_iam_member" "deployer_uses_cloud_build" {
  count = local.create_resources ? 1 : 0

  service_account_id = google_service_account.identity["cloud_build"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.identity["deployer"].email}"
}

resource "google_project_iam_member" "cloud_build_logging" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.identity["cloud_build"].email}"
}

resource "google_secret_manager_regional_secret" "runtime" {
  for_each = local.create_resources ? local.regional_secret_ids : {}

  project   = var.project_id
  location  = var.region
  secret_id = each.value
  labels    = local.labels

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_regional_secret_iam_member" "operator_access" {
  for_each = local.create_resources ? local.operator_secret_purposes : toset([])

  project   = var.project_id
  location  = var.region
  secret_id = google_secret_manager_regional_secret.runtime[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.identity["operator"].email}"
}

resource "google_secret_manager_regional_secret_iam_member" "judge_access" {
  for_each = local.create_resources ? local.judge_secret_purposes : toset([])

  project   = var.project_id
  location  = var.region
  secret_id = google_secret_manager_regional_secret.runtime[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.identity["judge"].email}"
}
