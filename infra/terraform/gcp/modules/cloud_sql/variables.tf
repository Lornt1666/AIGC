variable "project_id" {
  type        = string
  description = "Google Cloud project containing the isolated staging database."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid Google Cloud project ID."
  }
}

variable "region" {
  type        = string
  description = "Primary Cloud SQL region."
  default     = "northamerica-northeast2"
}

variable "instance_name" {
  type        = string
  description = "Cloud SQL instance name."
  default     = "aigc-staging-postgres"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,96}[a-z0-9]$", var.instance_name))
    error_message = "instance_name must use lowercase letters, digits, and hyphens."
  }
}

variable "network_name" {
  type        = string
  description = "Dedicated VPC network for private Cloud SQL connectivity."
  default     = "aigc-staging-sql"
}

variable "private_service_range_name" {
  type        = string
  description = "Reserved private services access range name."
  default     = "aigc-staging-sql-range"
}

variable "private_service_prefix_length" {
  type        = number
  description = "Prefix length for the automatically allocated private services range."
  default     = 20

  validation {
    condition     = var.private_service_prefix_length >= 16 && var.private_service_prefix_length <= 24
    error_message = "private_service_prefix_length must be between 16 and 24."
  }
}

variable "database_version" {
  type        = string
  description = "Cloud SQL PostgreSQL database version."
  default     = "POSTGRES_16"

  validation {
    condition     = can(regex("^POSTGRES_[0-9]+$", var.database_version))
    error_message = "database_version must use the POSTGRES_<MAJOR> format."
  }
}

variable "tier" {
  type        = string
  description = "Cloud SQL machine tier. The staging default is intentionally small and must be reviewed against workload requirements."
  default     = "db-f1-micro"
}

variable "availability_type" {
  type        = string
  description = "ZONAL for low-cost staging or REGIONAL for high availability."
  default     = "ZONAL"

  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.availability_type)
    error_message = "availability_type must be ZONAL or REGIONAL."
  }
}

variable "disk_type" {
  type        = string
  description = "Cloud SQL storage type."
  default     = "PD_SSD"

  validation {
    condition     = contains(["PD_SSD", "PD_HDD"], var.disk_type)
    error_message = "disk_type must be PD_SSD or PD_HDD."
  }
}

variable "disk_size_gb" {
  type        = number
  description = "Initial disk size in GiB."
  default     = 10

  validation {
    condition     = var.disk_size_gb >= 10
    error_message = "disk_size_gb must be at least 10 GiB."
  }
}

variable "deletion_protection" {
  type        = bool
  description = "Terraform deletion protection for the Cloud SQL instance."
  default     = true
}

variable "database_name" {
  type        = string
  description = "Initial application database name. No database user or password is created."
  default     = "aigc"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,62}$", var.database_name))
    error_message = "database_name must start with a lowercase letter and contain lowercase letters, digits, or underscores."
  }
}

variable "backup_start_time" {
  type        = string
  description = "Daily backup start time in UTC using HH:MM format."
  default     = "03:00"

  validation {
    condition     = can(regex("^(?:[01][0-9]|2[0-3]):[0-5][0-9]$", var.backup_start_time))
    error_message = "backup_start_time must use 24-hour HH:MM format."
  }
}

variable "backup_retention_count" {
  type        = number
  description = "Number of automated backups retained."
  default     = 7

  validation {
    condition     = var.backup_retention_count >= 1 && var.backup_retention_count <= 365
    error_message = "backup_retention_count must be between 1 and 365."
  }
}

variable "transaction_log_retention_days" {
  type        = number
  description = "Transaction-log retention used for point-in-time recovery."
  default     = 7

  validation {
    condition     = var.transaction_log_retention_days >= 1 && var.transaction_log_retention_days <= 7
    error_message = "transaction_log_retention_days must be between 1 and 7."
  }
}

variable "ssl_mode" {
  type        = string
  description = "Cloud SQL transport policy."
  default     = "ENCRYPTED_ONLY"

  validation {
    condition = contains([
      "ALLOW_UNENCRYPTED_AND_ENCRYPTED",
      "ENCRYPTED_ONLY",
      "TRUSTED_CLIENT_CERTIFICATE_REQUIRED",
    ], var.ssl_mode)
    error_message = "ssl_mode must be a supported Cloud SQL SSL mode."
  }
}

variable "maintenance_day" {
  type        = number
  description = "Maintenance day, where 1 is Monday and 7 is Sunday."
  default     = 7

  validation {
    condition     = var.maintenance_day >= 1 && var.maintenance_day <= 7
    error_message = "maintenance_day must be between 1 and 7."
  }
}

variable "maintenance_hour" {
  type        = number
  description = "Maintenance hour in UTC."
  default     = 4

  validation {
    condition     = var.maintenance_hour >= 0 && var.maintenance_hour <= 23
    error_message = "maintenance_hour must be between 0 and 23."
  }
}

variable "query_insights_enabled" {
  type        = bool
  description = "Enable Query Insights without recording client addresses."
  default     = true
}

variable "runtime_service_account_email" {
  type        = string
  description = "Optional runtime service-account email granted Cloud SQL client and instance-user roles."
  default     = ""

  validation {
    condition = (
      var.runtime_service_account_email == "" ||
      can(regex("^[a-z0-9-]+@[a-z0-9-]+\\.iam\\.gserviceaccount\\.com$", var.runtime_service_account_email))
    )
    error_message = "runtime_service_account_email must be empty or a valid service-account email."
  }
}

variable "database_flags" {
  type        = map(string)
  description = "Reviewed PostgreSQL database flags. IAM database authentication is enabled by default."
  default = {
    "cloudsql.iam_authentication" = "on"
  }
}

variable "labels" {
  type        = map(string)
  description = "Additional resource labels."
  default     = {}
}
