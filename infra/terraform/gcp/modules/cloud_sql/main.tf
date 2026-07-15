locals {
  required_services = toset([
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
  ])

  runtime_roles = var.runtime_service_account_email == "" ? toset([]) : toset([
    "roles/cloudsql.client",
    "roles/cloudsql.instanceUser",
  ])

  labels = merge(
    {
      component  = "cloud-sql"
      environment = "staging"
      managed_by = "terraform"
      system     = "aigc"
    },
    var.labels,
  )
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "cloud_sql" {
  project                 = var.project_id
  name                    = var.network_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.required]
}

resource "google_compute_global_address" "private_service_range" {
  project       = var.project_id
  name          = var.private_service_range_name
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.private_service_prefix_length
  network       = google_compute_network.cloud_sql.id

  depends_on = [google_project_service.required]
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.cloud_sql.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_range.name]

  depends_on = [google_project_service.required]
}

resource "google_sql_database_instance" "postgres" {
  project             = var.project_id
  name                = var.instance_name
  region              = var.region
  database_version    = var.database_version
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.tier
    availability_type = var.availability_type
    activation_policy = "ALWAYS"
    disk_type          = var.disk_type
    disk_size          = var.disk_size_gb
    disk_autoresize    = true
    user_labels        = local.labels

    backup_configuration {
      enabled                        = true
      start_time                     = var.backup_start_time
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = var.transaction_log_retention_days

      backup_retention_settings {
        retained_backups = var.backup_retention_count
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.cloud_sql.id
      allocated_ip_range                            = google_compute_global_address.private_service_range.name
      enable_private_path_for_google_cloud_services = false
      ssl_mode                                      = var.ssl_mode
    }

    dynamic "database_flags" {
      for_each = var.database_flags
      content {
        name  = database_flags.key
        value = database_flags.value
      }
    }

    insights_config {
      query_insights_enabled  = var.query_insights_enabled
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = false
    }

    maintenance_window {
      day          = var.maintenance_day
      hour         = var.maintenance_hour
      update_track = "stable"
    }
  }

  depends_on = [
    google_project_service.required,
    google_service_networking_connection.private_vpc_connection,
  ]

  timeouts {
    create = "60m"
    update = "60m"
    delete = "60m"
  }
}

resource "google_sql_database" "application" {
  project  = var.project_id
  name     = var.database_name
  instance = google_sql_database_instance.postgres.name
}

resource "google_project_iam_member" "runtime" {
  for_each = local.runtime_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.runtime_service_account_email}"

  depends_on = [google_project_service.required]
}
