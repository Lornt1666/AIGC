locals {
  github_repository          = "Lornt1666/AIGC"
  github_repository_id       = "1287333065"
  github_repository_owner_id = "236225491"
  github_wif_pool_id         = "${var.resource_prefix}-gha"
  github_wif_provider_id     = "github"
  github_release_workflow    = "${local.github_repository}/.github/workflows/aigc-release-staging.yml@refs/heads/main"
  github_release_environment = "aigc-nexus-staging"

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
  ])

  canary_secret_access = {
    gemini_runtime_control = {
      purpose         = "runtime_control_dsn"
      service_account = "canary_gemini"
    }
    openai_runtime_control = {
      purpose         = "runtime_control_dsn"
      service_account = "canary_openai"
    }
    openai_provider_credential = {
      purpose         = "openai_api_key"
      service_account = "canary_openai"
    }
  }
}

resource "google_iam_workload_identity_pool" "github" {
  count = local.create_resources ? 1 : 0

  project                   = var.project_id
  workload_identity_pool_id = local.github_wif_pool_id
  display_name              = "AIGC GitHub staging"
  description               = "Keyless GitHub Actions identity for the governed AIGC release train."
  disabled                  = false

  depends_on = [
    google_project_service.platform_control_plane,
    google_project_service.required,
  ]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count = local.create_resources ? 1 : 0

  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = local.github_wif_provider_id
  display_name                       = "AIGC GitHub OIDC"
  description                        = "Repository-ID and owner-ID restricted GitHub OIDC provider."

  attribute_mapping = {
    "google.subject"                  = "assertion.sub"
    "attribute.repository"            = "assertion.repository"
    "attribute.repository_id"         = "assertion.repository_id"
    "attribute.repository_owner_id"   = "assertion.repository_owner_id"
    "attribute.ref"                   = "assertion.ref"
    "attribute.workflow_ref"          = "assertion.workflow_ref"
    "attribute.event_name"            = "assertion.event_name"
    "attribute.environment"           = "assertion.environment"
    "attribute.repository_visibility" = "assertion.repository_visibility"
    "attribute.actor_id"              = "assertion.actor_id"
  }

  attribute_condition = join(" && ", [
    "assertion.repository == '${local.github_repository}'",
    "assertion.repository_id == '${local.github_repository_id}'",
    "assertion.repository_owner_id == '${local.github_repository_owner_id}'",
    "assertion.repository_visibility == 'private'",
    "assertion.ref_type == 'branch'",
    "assertion.ref == 'refs/heads/main'",
    "assertion.workflow_ref == '${local.github_release_workflow}'",
    "assertion.event_name == 'workflow_dispatch'",
    "assertion.environment == '${local.github_release_environment}'",
  ])

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif_security_review" {
  count = local.create_resources ? 1 : 0

  service_account_id = google_service_account.identity["security_review"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github[0].workload_identity_pool_id}/attribute.repository_id/${local.github_repository_id}"
}

resource "google_project_iam_custom_role" "canary_job_provisioner" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_job_provisioner"
  title       = "AIGC governed canary job provisioner"
  description = "Create, update, and verify dormant governed canary jobs; excludes execution, override, deletion, and IAM-policy mutation."
  permissions = [
    "run.jobs.create",
    "run.jobs.get",
    "run.jobs.update",
  ]
}

resource "google_project_iam_custom_role" "canary_provisioner_support" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_provisioner_support"
  title       = "AIGC governed canary provisioner support"
  description = "Read project and Cloud Run operation state and consume enabled APIs; contains no job execution or resource mutation authority."
  permissions = [
    "resourcemanager.projects.get",
    "resourcemanager.projects.getIamPolicy",
    "iam.serviceAccounts.getIamPolicy",
    "run.operations.get",
    "serviceusage.services.use",
  ]
}

resource "google_project_iam_member" "canary_provisioner_support" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.canary_provisioner_support[0].name
  member  = "serviceAccount:${google_service_account.identity["canary_provisioner"].email}"
}

resource "google_project_iam_custom_role" "canary_job_executor" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_job_executor"
  title       = "AIGC governed canary job executor"
  description = "Read exact job and job IAM evidence. Execution authority is granted only by a conditioned roles/run.invoker binding on one post-provisioned job."
  permissions = [
    "run.jobs.get",
    "run.jobs.getIamPolicy",
  ]
}

resource "google_project_iam_member" "canary_job_executor" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.canary_job_executor[0].name
  member  = "serviceAccount:${google_service_account.identity["canary_executor"].email}"
}

resource "google_project_iam_custom_role" "canary_job_iam_binder" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_job_iam_binder"
  title       = "AIGC exact-job canary IAM binder"
  description = "Get and set one existing Cloud Run job IAM policy. This inert role is never project-bound and has no WIF, TokenCreator, or client-JIT path; only a non-impersonable trusted broker may receive an expiring exact-job binding."
  permissions = [
    "run.jobs.get",
    "run.jobs.getIamPolicy",
    "run.jobs.setIamPolicy",
  ]
}

resource "google_project_iam_custom_role" "canary_executor_evidence_reader" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_executor_evidence"
  title       = "AIGC governed canary execution evidence reader"
  description = "Read canary execution, operation, and non-private log evidence; contains no job override, mutation, cancellation, or deletion authority."
  permissions = [
    "logging.logEntries.list",
    "run.executions.get",
    "run.operations.get",
  ]
}

resource "google_project_iam_member" "canary_executor_evidence_reader" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.canary_executor_evidence_reader[0].name
  member  = "serviceAccount:${google_service_account.identity["canary_executor"].email}"
}

resource "google_project_iam_custom_role" "canary_binding_consumption_reader" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_binding_receipt_reader"
  title       = "AIGC canary binding-consumption reader"
  description = "Read immutable one-use canary job binding-consumption objects; excludes list, create, update, and delete."
  permissions = ["storage.objects.get"]
}

resource "google_storage_bucket_iam_member" "canary_executor_binding_consumption_reader" {
  count = local.create_resources ? 1 : 0

  bucket = google_storage_bucket.regional["receipts"].name
  role   = google_project_iam_custom_role.canary_binding_consumption_reader[0].name
  member = "serviceAccount:${google_service_account.identity["canary_executor"].email}"

  condition {
    title       = "read_immutable_canary_binding_consumption"
    description = "Restrict executor reads to one-use exact-job binding consumption receipts."
    expression  = "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.regional["receipts"].name}/objects/canary-job-execution-bindings/')"
  }
}

resource "google_storage_bucket_iam_member" "canary_binder_binding_consumption_reader" {
  count = local.create_resources ? 1 : 0

  bucket = google_storage_bucket.regional["receipts"].name
  role   = google_project_iam_custom_role.canary_binding_consumption_reader[0].name
  member = "serviceAccount:${google_service_account.identity["canary_binder"].email}"

  condition {
    title       = "read_own_canary_binding_consumption"
    description = "Restrict trusted-broker readback to immutable binding-consumption receipts."
    expression  = "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.regional["receipts"].name}/objects/canary-job-execution-bindings/')"
  }
}

resource "google_project_iam_custom_role" "canary_image_reader" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_image_reader"
  title       = "AIGC governed canary image reader"
  description = "Read the exact immutable canary image from the Montréal runtime repository without project-wide registry read authority."
  permissions = [
    "artifactregistry.dockerimages.get",
    "artifactregistry.dockerimages.list",
    "artifactregistry.repositories.downloadArtifacts",
    "artifactregistry.repositories.get",
  ]
}

resource "google_project_iam_custom_role" "canary_network_inspector" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_network_inspector"
  title       = "AIGC governed canary network inspector"
  description = "Read the exact network metadata needed to attach a dormant canary job; excludes network mutation."
  permissions = ["compute.networks.get"]
}

resource "google_project_iam_member" "canary_provisioner_network_inspector" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.canary_network_inspector[0].name
  member  = "serviceAccount:${google_service_account.identity["canary_provisioner"].email}"
}

resource "google_project_iam_custom_role" "canary_subnetwork_user" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_subnetwork_user"
  title       = "AIGC governed canary subnetwork user"
  description = "Inspect and use only the exact Montréal canary subnetwork; excludes external-IP and network mutation authority."
  permissions = [
    "compute.subnetworks.get",
    "compute.subnetworks.use",
  ]
}

resource "google_storage_bucket_iam_member" "canary_provisioning_receipt_creator" {
  count = local.create_resources ? 1 : 0

  bucket = google_storage_bucket.regional["receipts"].name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.identity["canary_provisioner"].email}"
}

resource "google_storage_bucket_iam_member" "canary_binding_receipt_creator" {
  count = local.create_resources ? 1 : 0

  bucket = google_storage_bucket.regional["receipts"].name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.identity["canary_binder"].email}"
}

resource "google_storage_bucket_iam_member" "canary_receipt_publisher_creator" {
  count = local.create_resources ? 1 : 0

  bucket = google_storage_bucket.regional["receipts"].name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.identity["canary_publisher"].email}"
}

resource "google_project_iam_custom_role" "release_deployer" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_release_deployer"
  title       = "AIGC fail-closed release inspector"
  description = "Read preprovisioned release resources only. All build, workload, SBOM, evidence-write, run, and actAs mutations remain blocked pending a trusted attached broker."
  permissions = [
    "cloudbuild.builds.get",
    "cloudbuild.builds.list",
    "cloudsql.instances.get",
    "iam.serviceAccounts.get",
    "logging.logEntries.list",
    "resourcemanager.projects.get",
    "run.executions.get",
    "run.executions.list",
    "run.jobs.get",
    "run.jobs.list",
    "run.operations.get",
    "run.revisions.get",
    "run.revisions.list",
    "run.services.get",
    "run.services.getIamPolicy",
    "run.services.list",
    "serviceusage.services.use",
  ]
}

resource "google_project_iam_member" "deployer_release" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.release_deployer[0].name
  member  = "serviceAccount:${google_service_account.identity["deployer"].email}"
}

resource "google_project_iam_custom_role" "sbom_metadata_loader" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_sbom_metadata_loader"
  title       = "AIGC exact SBOM metadata loader"
  description = "Create and verify one SBOM reference for an immutable image; excludes update, delete, and IAM-policy mutation."
  permissions = [
    "containeranalysis.notes.attachOccurrence",
    "containeranalysis.notes.create",
    "containeranalysis.notes.get",
    "containeranalysis.notes.list",
    "containeranalysis.occurrences.create",
    "containeranalysis.occurrences.get",
    "containeranalysis.occurrences.list",
  ]
}

resource "google_project_iam_custom_role" "build_source_writer" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_build_source_writer"
  title       = "AIGC create-only build source writer"
  description = "Upload a new exact-tree source object without read, overwrite, or delete authority."
  permissions = [
    "storage.buckets.get",
    "storage.objects.create",
  ]
}

resource "google_project_iam_custom_role" "build_source_reader" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_build_source_reader"
  title       = "AIGC exact build source reader"
  description = "Read admitted build source objects without list, write, or delete authority."
  permissions = [
    "storage.buckets.get",
    "storage.objects.get",
  ]
}

resource "google_project_iam_custom_role" "sbom_object_writer" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_sbom_object_writer"
  title       = "AIGC create-only SBOM object writer"
  description = "Upload a new SBOM object to the precreated Montréal evidence bucket without read, overwrite, list, or delete authority."
  permissions = [
    "storage.buckets.get",
    "storage.objects.create",
  ]
}

resource "google_project_iam_custom_role" "sbom_image_reader" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_sbom_image_reader"
  title       = "AIGC exact release-image reader"
  description = "Pull an immutable release image from the exact Montréal repository without project-wide registry read authority."
  permissions = [
    "artifactregistry.dockerimages.get",
    "artifactregistry.dockerimages.list",
    "artifactregistry.repositories.downloadArtifacts",
    "artifactregistry.repositories.get",
  ]
}

resource "google_project_iam_member" "cloud_build_logging" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.identity["cloud_build"].email}"
}

resource "google_storage_bucket_iam_member" "cloud_build_source_reader" {
  count = local.create_resources ? 1 : 0

  bucket = google_storage_bucket.regional["build"].name
  role   = google_project_iam_custom_role.build_source_reader[0].name
  member = "serviceAccount:${google_service_account.identity["cloud_build"].email}"
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

resource "google_secret_manager_regional_secret_iam_member" "canary_access" {
  for_each = local.create_resources ? local.canary_secret_access : {}

  project   = var.project_id
  location  = var.region
  secret_id = google_secret_manager_regional_secret.runtime[each.value.purpose].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.identity[each.value.service_account].email}"
}
