// --- providers.tf ---
provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
}

// --- locals.tf ---
locals {
  create_resources = var.resource_creation_authorized

  required_apis = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "containeranalysis.googleapis.com",
    "containerscanning.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "cloudkms.googleapis.com",
  ])

  labels = {
    system            = "aigc"
    environment       = "staging"
    jurisdiction      = "quebec"
    region            = "northamerica-northeast1"
    managed_by        = "terraform"
    release_sha_short = substr(var.release_sha, 0, 12)
  }

  names = {
    network             = "${var.resource_prefix}-vpc"
    subnet              = "${var.resource_prefix}-subnet"
    artifact_repository = "${var.resource_prefix}-runtime"
    operator_service    = "${var.resource_prefix}-operator"
    judge_service       = "${var.resource_prefix}-judge"
    sql_instance        = "${var.resource_prefix}-control"
    database            = "aigc_control"
    evidence_bucket     = "${var.project_id}-${var.resource_prefix}-evidence"
    judge_bucket        = "${var.project_id}-${var.resource_prefix}-judge"
    receipt_bucket      = "${var.project_id}-${var.resource_prefix}-receipts"
    build_source_bucket = "${var.project_id}-${var.resource_prefix}-build-source"
    log_bucket          = "${var.resource_prefix}-logs"
    kms_key_ring        = "${var.resource_prefix}-keys"
  }

  service_accounts = {
    deployer = {
      account_id   = "${var.resource_prefix}-deployer"
      display_name = "AIGC Québec staging deployer"
    }
    cloud_build = {
      account_id   = "${var.resource_prefix}-build"
      display_name = "AIGC Québec regional build"
    }
    operator = {
      account_id   = "${var.resource_prefix}-operator"
      display_name = "AIGC Québec operator runtime"
    }
    canary_gemini = {
      account_id   = "${var.resource_prefix}-can-gem"
      display_name = "AIGC Québec Gemini canary runtime"
    }
    canary_openai = {
      account_id   = "${var.resource_prefix}-can-oai"
      display_name = "AIGC Québec OpenAI canary runtime"
    }
    canary_provisioner = {
      account_id   = "${var.resource_prefix}-can-prov"
      display_name = "AIGC Québec governed canary job provisioner"
    }
    canary_binder = {
      account_id   = "${var.resource_prefix}-can-bind"
      display_name = "AIGC Québec exact-job canary IAM binder"
    }
    canary_executor = {
      account_id   = "${var.resource_prefix}-can-exec"
      display_name = "AIGC Québec governed canary job executor"
    }
    canary_publisher = {
      account_id   = "${var.resource_prefix}-can-pub"
      display_name = "AIGC Québec create-only canary receipt publisher"
    }
    judge = {
      account_id   = "${var.resource_prefix}-judge"
      display_name = "AIGC Québec judge runtime"
    }
    security_review = {
      account_id   = "${var.resource_prefix}-security"
      display_name = "AIGC Québec security review"
    }
    authority_signer = {
      account_id   = "${var.resource_prefix}-signer"
      display_name = "AIGC Québec canary authority signer"
    }
  }
}

// --- project_services.tf ---
resource "google_project_service" "required" {
  for_each = local.create_resources ? local.required_apis : toset([])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

// --- service_accounts.tf ---
resource "google_service_account" "identity" {
  for_each = local.create_resources ? local.service_accounts : {}

  project      = var.project_id
  account_id   = each.value.account_id
  display_name = each.value.display_name
  description  = "Keyless managed identity for AIGC staging in Montréal."

  depends_on = [google_project_service.required]
}

// --- artifact_registry.tf ---
resource "google_artifact_registry_repository" "runtime" {
  count = local.create_resources ? 1 : 0

  project       = var.project_id
  location      = var.region
  repository_id = local.names.artifact_repository
  description   = "Immutable AIGC staging images admitted by exact-SHA review."
  format        = "DOCKER"
  labels        = local.labels

  docker_config {
    immutable_tags = true
  }

  depends_on = [google_project_service.required]
}

resource "google_artifact_registry_repository_iam_member" "build_writer" {
  count = local.create_resources ? 1 : 0

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.runtime[0].name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.identity["cloud_build"].email}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_reader" {
  count = local.create_resources ? 1 : 0

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.runtime[0].name
  role       = google_project_iam_custom_role.sbom_image_reader[0].name
  member     = "serviceAccount:${google_service_account.identity["deployer"].email}"
}

resource "google_artifact_registry_repository_iam_member" "canary_provisioner_image_reader" {
  count = local.create_resources ? 1 : 0

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.runtime[0].name
  role       = google_project_iam_custom_role.canary_image_reader[0].name
  member     = "serviceAccount:${google_service_account.identity["canary_provisioner"].email}"
}

// --- network.tf ---
resource "google_compute_network" "main" {
  count = local.create_resources ? 1 : 0

  project                 = var.project_id
  name                    = local.names.network
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "serverless" {
  count = local.create_resources ? 1 : 0

  project                  = var.project_id
  name                     = local.names.subnet
  region                   = var.region
  network                  = google_compute_network.main[0].id
  ip_cidr_range            = "10.70.0.0/24"
  private_ip_google_access = true
}

resource "google_compute_subnetwork_iam_member" "canary_provisioner_subnetwork_user" {
  count = local.create_resources ? 1 : 0

  project    = var.project_id
  region     = var.region
  subnetwork = google_compute_subnetwork.serverless[0].name
  role       = google_project_iam_custom_role.canary_subnetwork_user[0].name
  member     = "serviceAccount:${google_service_account.identity["canary_provisioner"].email}"
}

resource "google_compute_global_address" "private_services" {
  count = local.create_resources ? 1 : 0

  project       = var.project_id
  name          = "${var.resource_prefix}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main[0].id
}

resource "google_service_networking_connection" "private_services" {
  count = local.create_resources ? 1 : 0

  network                 = google_compute_network.main[0].id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services[0].name]
}

// --- cloud_sql.tf ---
resource "google_sql_database_instance" "control" {
  count = local.create_resources ? 1 : 0

  project             = var.project_id
  name                = local.names.sql_instance
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true

  settings {
    tier              = var.database_tier
    availability_type = "REGIONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.database_disk_gb
    disk_autoresize   = false
    user_labels       = local.labels

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.main[0].id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "07:00"
      location                       = var.region
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    maintenance_window {
      day          = 7
      hour         = 8
      update_track = "stable"
    }
  }

  depends_on = [google_service_networking_connection.private_services]
}

resource "google_sql_database" "control" {
  count = local.create_resources ? 1 : 0

  project  = var.project_id
  name     = local.names.database
  instance = google_sql_database_instance.control[0].name
}

// --- storage.tf ---
resource "google_storage_bucket" "regional" {
  for_each = local.create_resources ? {
    evidence = local.names.evidence_bucket
    judge    = local.names.judge_bucket
    receipts = local.names.receipt_bucket
    build    = local.names.build_source_bucket
  } : {}

  project                     = var.project_id
  name                        = each.value
  location                    = upper(var.region)
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels

  versioning {
    enabled = true
  }

  retention_policy {
    retention_period = var.evidence_retention_days * 86400
    is_locked        = false
  }

  lifecycle_rule {
    condition {
      age = var.evidence_retention_days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "operator_evidence_creator" {
  count = local.create_resources ? 1 : 0

  bucket = google_storage_bucket.regional["evidence"].name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.identity["operator"].email}"
}

resource "google_storage_bucket_iam_member" "judge_receipt_reader" {
  count = local.create_resources ? 1 : 0

  bucket = google_storage_bucket.regional["judge"].name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.identity["judge"].email}"
}

resource "google_storage_bucket_iam_member" "security_review_viewer" {
  for_each = local.create_resources ? google_storage_bucket.regional : {}

  bucket = each.value.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.identity["security_review"].email}"
}

// --- kms.tf ---
resource "google_kms_key_ring" "main" {
  count = local.create_resources ? 1 : 0

  project  = var.project_id
  name     = local.names.kms_key_ring
  location = var.region

  depends_on = [google_project_service.required]
}

resource "google_kms_crypto_key" "evidence" {
  count = local.create_resources ? 1 : 0

  name            = "evidence"
  key_ring        = google_kms_key_ring.main[0].id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "database" {
  count = local.create_resources ? 1 : 0

  name            = "database"
  key_ring        = google_kms_key_ring.main[0].id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "canary_authority" {
  count = local.create_resources ? 1 : 0

  name                          = "${var.resource_prefix}-canary-authority"
  key_ring                      = google_kms_key_ring.main[0].id
  purpose                       = "ASYMMETRIC_SIGN"
  skip_initial_version_creation = true

  version_template {
    algorithm        = "RSA_SIGN_PSS_2048_SHA256"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_version" "canary_authority_v1" {
  count = local.create_resources ? 1 : 0

  crypto_key       = google_kms_crypto_key.canary_authority[0].id
  algorithm        = "RSA_SIGN_PSS_2048_SHA256"
  protection_level = "SOFTWARE"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "canary_authority_signer" {
  count = local.create_resources ? 1 : 0

  crypto_key_id = google_kms_crypto_key.canary_authority[0].id
  role          = "roles/cloudkms.signer"
  member        = "serviceAccount:${google_service_account.identity["authority_signer"].email}"
}

resource "google_kms_crypto_key_iam_member" "canary_authority_public_key_viewer" {
  for_each = local.create_resources ? {
    authority_signer   = google_service_account.identity["authority_signer"].email
    deployer           = google_service_account.identity["deployer"].email
    canary_gemini      = google_service_account.identity["canary_gemini"].email
    canary_openai      = google_service_account.identity["canary_openai"].email
    canary_provisioner = google_service_account.identity["canary_provisioner"].email
    canary_binder      = google_service_account.identity["canary_binder"].email
    canary_executor    = google_service_account.identity["canary_executor"].email
    canary_publisher   = google_service_account.identity["canary_publisher"].email
  } : {}

  crypto_key_id = google_kms_crypto_key.canary_authority[0].id
  role          = "roles/cloudkms.publicKeyViewer"
  member        = "serviceAccount:${each.value}"
}

// --- logging.tf ---
resource "google_logging_project_bucket_config" "regional" {
  count = local.create_resources ? 1 : 0

  project        = var.project_id
  location       = var.region
  bucket_id      = local.names.log_bucket
  retention_days = var.log_retention_days
  description    = "Regional AIGC staging log storage in Montréal."
}

resource "google_logging_project_sink" "regional" {
  count = local.create_resources ? 1 : 0

  project                = var.project_id
  name                   = "${var.resource_prefix}-regional"
  destination            = "logging.googleapis.com/projects/${var.project_id}/locations/${var.region}/buckets/${google_logging_project_bucket_config.regional[0].bucket_id}"
  unique_writer_identity = true
  filter                 = "resource.type=(\"cloud_run_revision\" OR \"cloudsql_database\" OR \"build\")"
}

resource "google_project_iam_member" "log_sink_writer" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = "roles/logging.bucketWriter"
  member  = google_logging_project_sink.regional[0].writer_identity
}

// --- iam.tf ---
resource "google_project_iam_custom_role" "canary_gemini_predict" {
  count = local.create_resources ? 1 : 0

  project     = var.project_id
  role_id     = "${replace(var.resource_prefix, "-", "_")}_canary_predict"
  title       = "AIGC Gemini canary predictor"
  description = "Perform one governed Gemini prompt request; excludes model, endpoint, tuning, and dataset management."
  permissions = ["aiplatform.endpoints.predict"]
}

resource "google_project_iam_member" "canary_gemini_vertex" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.canary_gemini_predict[0].name
  member  = "serviceAccount:${google_service_account.identity["canary_gemini"].email}"
}

resource "google_project_iam_member" "operator_sql_client" {
  count = local.create_resources ? 1 : 0

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.identity["operator"].email}"
}

resource "google_project_iam_member" "canary_sql_client" {
  for_each = local.create_resources ? {
    canary_gemini = google_service_account.identity["canary_gemini"].email
    canary_openai = google_service_account.identity["canary_openai"].email
  } : {}

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${each.value}"
}

resource "google_project_iam_member" "runtime_logging" {
  for_each = local.create_resources ? {
    operator      = google_service_account.identity["operator"].email
    judge         = google_service_account.identity["judge"].email
    canary_gemini = google_service_account.identity["canary_gemini"].email
    canary_openai = google_service_account.identity["canary_openai"].email
  } : {}

  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${each.value}"
}

resource "google_project_iam_member" "runtime_metrics" {
  for_each = local.create_resources ? {
    operator = google_service_account.identity["operator"].email
    judge    = google_service_account.identity["judge"].email
  } : {}

  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${each.value}"
}

// --- budgets.tf ---
resource "google_billing_budget" "staging" {
  count = local.create_resources ? 1 : 0

  billing_account = var.billing_account_id
  display_name    = "AIGC Québec staging monthly ceiling"

  budget_filter {
    projects               = ["projects/${var.project_number}"]
    calendar_period        = "MONTH"
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "CAD"
      units         = tostring(floor(var.monthly_budget_cad))
      nanos         = 0
    }
  }

  dynamic "threshold_rules" {
    for_each = toset([0.50, 0.75, 0.90, 1.00])
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  all_updates_rule {
    monitoring_notification_channels = var.budget_notification_channels
    disable_default_iam_recipients   = false
  }

  lifecycle {
    precondition {
      condition     = length(var.budget_notification_channels) > 0
      error_message = "A material staging budget requires a reviewed notification channel."
    }
  }
}

// --- cloud_run.tf ---
# Cloud Run services are intentionally not created by this foundation root.
# The exact PR/head in the authorization receipt controls the governed
# immutable-digest deployment procedure, which must:
# - build in northamerica-northeast1;
# - deploy separate operator and judge candidates;
# - keep unauthenticated access disabled;
# - assign no public access;
# - perform no live Gemini call;
# - retain an immutable deployment receipt.
#
# This separation prevents Terraform foundation authorization from silently
# becoming application deployment authority.
# Blocking variable validations keep public access, provider calls, and
# production activation false independently of this descriptive boundary.

// --- monitoring.tf ---
# Monitoring policies are created after exact metric names, notification channels,
# and service revisions exist. The authorization packet requires alerts for:
# authentication failures, IAM changes, budget thresholds, unusual egress,
# Cloud Run 5xx rate, emergency-stop changes, evidence-write failures, Cloud SQL
# availability, deployment changes, and regional drift.
