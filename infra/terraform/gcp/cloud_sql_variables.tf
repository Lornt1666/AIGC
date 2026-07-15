variable "cloud_sql_enabled" {
  type        = bool
  description = "Explicit subsystem gate. Must remain false until a separately authorized staging action."
  default     = false
}

variable "cloud_sql_instance_name" {
  type        = string
  description = "Cloud SQL staging instance name."
  default     = "aigc-staging-postgres"
}

variable "cloud_sql_network_name" {
  type        = string
  description = "Dedicated private network for the staging Cloud SQL instance."
  default     = "aigc-staging-sql"
}

variable "cloud_sql_private_service_range_name" {
  type        = string
  description = "Private services access range name."
  default     = "aigc-staging-sql-range"
}

variable "cloud_sql_private_service_prefix_length" {
  type        = number
  description = "Prefix length for the private services access allocation."
  default     = 20

  validation {
    condition = (
      var.cloud_sql_private_service_prefix_length >= 16 &&
      var.cloud_sql_private_service_prefix_length <= 24
    )
    error_message = "cloud_sql_private_service_prefix_length must be between 16 and 24."
  }
}

variable "cloud_sql_database_version" {
  type        = string
  description = "Cloud SQL PostgreSQL major version."
  default     = "POSTGRES_16"
}

variable "cloud_sql_tier" {
  type        = string
  description = "Staging Cloud SQL machine tier."
  default     = "db-f1-micro"
}

variable "cloud_sql_availability_type" {
  type        = string
  description = "ZONAL for bounded staging or REGIONAL for high availability."
  default     = "ZONAL"

  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.cloud_sql_availability_type)
    error_message = "cloud_sql_availability_type must be ZONAL or REGIONAL."
  }
}

variable "cloud_sql_disk_type" {
  type        = string
  description = "Cloud SQL disk type."
  default     = "PD_SSD"

  validation {
    condition     = contains(["PD_SSD", "PD_HDD"], var.cloud_sql_disk_type)
    error_message = "cloud_sql_disk_type must be PD_SSD or PD_HDD."
  }
}

variable "cloud_sql_disk_size_gb" {
  type        = number
  description = "Initial Cloud SQL disk size in GiB."
  default     = 10

  validation {
    condition     = var.cloud_sql_disk_size_gb >= 10
    error_message = "cloud_sql_disk_size_gb must be at least 10 GiB."
  }
}

variable "cloud_sql_deletion_protection" {
  type        = bool
  description = "Terraform deletion protection for the staging instance."
  default     = true
}

variable "cloud_sql_database_name" {
  type        = string
  description = "Initial application database name."
  default     = "aigc"
}

variable "cloud_sql_backup_start_time" {
  type        = string
  description = "Daily automated backup start time in UTC."
  default     = "03:00"
}

variable "cloud_sql_backup_retention_count" {
  type        = number
  description = "Automated backup retention count."
  default     = 7
}

variable "cloud_sql_transaction_log_retention_days" {
  type        = number
  description = "Transaction-log retention for point-in-time recovery."
  default     = 7

  validation {
    condition = (
      var.cloud_sql_transaction_log_retention_days >= 1 &&
      var.cloud_sql_transaction_log_retention_days <= 7
    )
    error_message = "cloud_sql_transaction_log_retention_days must be between 1 and 7."
  }
}

variable "cloud_sql_ssl_mode" {
  type        = string
  description = "Cloud SQL encrypted transport policy."
  default     = "ENCRYPTED_ONLY"
}

variable "cloud_sql_maintenance_day" {
  type        = number
  description = "Maintenance day, where 1 is Monday and 7 is Sunday."
  default     = 7
}

variable "cloud_sql_maintenance_hour" {
  type        = number
  description = "Maintenance hour in UTC."
  default     = 4
}

variable "cloud_sql_query_insights_enabled" {
  type        = bool
  description = "Enable Query Insights without client-address recording."
  default     = true
}

variable "cloud_sql_runtime_service_account_email" {
  type        = string
  description = "Optional runtime service account granted Cloud SQL client and instance-user roles."
  default     = ""
}

variable "cloud_sql_database_flags" {
  type        = map(string)
  description = "Reviewed PostgreSQL database flags."
  default = {
    "cloudsql.iam_authentication" = "on"
  }
}

variable "cloud_sql_labels" {
  type        = map(string)
  description = "Additional labels for Cloud SQL staging resources."
  default     = {}
}
