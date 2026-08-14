variable "project_id" {
  description = "Existing Google Cloud staging project ID. This root never creates a project."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be an exact Google Cloud project ID."
  }
}

variable "project_number" {
  description = "Exact numeric Google Cloud project number used by budget and service-agent bindings."
  type        = string
  validation {
    condition     = can(regex("^[1-9][0-9]{5,20}$", var.project_number))
    error_message = "project_number must be an exact numeric project number."
  }
}

variable "billing_account_id" {
  description = "Exact billing account ID; not a payment credential."
  type        = string
  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "billing_account_id must use the canonical XXXXXX-XXXXXX-XXXXXX form."
  }
}

variable "region" {
  description = "Strict Québec staging region."
  type        = string
  default     = "northamerica-northeast1"
  validation {
    condition     = var.region == "northamerica-northeast1"
    error_message = "Only Montréal northamerica-northeast1 is authorized by this foundation."
  }
}

variable "resource_prefix" {
  description = "Lowercase prefix for staging resource names."
  type        = string
  default     = "aigc-qc-stg"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,18}$", var.resource_prefix))
    error_message = "resource_prefix must be a bounded lowercase resource prefix of at most 19 characters."
  }
}

variable "resource_creation_authorized" {
  description = "Exact human authorization to create foundational staging resources."
  type        = bool
  default     = false
}

variable "staging_deployment_authorized" {
  description = "Separate no-production deployment authorization. Terraform does not perform the deployment."
  type        = bool
  default     = false
}

variable "production_activation_authorized" {
  description = "Must remain false in this staging foundation."
  type        = bool
  default     = false
  validation {
    condition     = var.production_activation_authorized == false
    error_message = "Production activation is prohibited."
  }
}

variable "public_access_authorized" {
  description = "Must remain false. No allUsers or allAuthenticatedUsers bindings are permitted."
  type        = bool
  default     = false
  validation {
    condition     = var.public_access_authorized == false
    error_message = "Public access is prohibited."
  }
}

variable "live_model_call_authorized" {
  description = "Must remain false. A one-use canary requires a separate permit."
  type        = bool
  default     = false
  validation {
    condition     = var.live_model_call_authorized == false
    error_message = "A live model call is prohibited by this foundation."
  }
}

variable "cross_region_replication_authorized" {
  description = "Must remain false until Toronto disaster recovery is separately approved."
  type        = bool
  default     = false
  validation {
    condition     = var.cross_region_replication_authorized == false
    error_message = "Cross-region replication is prohibited by the current strict Québec policy."
  }
}

variable "service_account_key_creation_authorized" {
  description = "Must remain false. Use attached identities and short-lived federation."
  type        = bool
  default     = false
  validation {
    condition     = var.service_account_key_creation_authorized == false
    error_message = "Downloadable service-account keys are prohibited."
  }
}

variable "monthly_budget_cad" {
  description = "Owner-approved monthly ceiling in CAD. Google Cloud budgets are alerts, not guaranteed hard caps."
  type        = number
  default     = 200
  validation {
    condition     = var.monthly_budget_cad > 0 && var.monthly_budget_cad <= 200
    error_message = "monthly_budget_cad must be greater than zero and no more than CAD 200."
  }
}

variable "budget_notification_channels" {
  description = "Pre-existing Monitoring notification channel resource names."
  type        = list(string)
  default     = []
}

variable "release_sha" {
  description = "Admitted exact 40-character Git release SHA."
  type        = string
  validation {
    condition     = can(regex("^[a-f0-9]{40}$", var.release_sha))
    error_message = "release_sha must be an exact lowercase 40-character Git SHA."
  }
}

variable "release_tree_sha" {
  description = "Admitted exact 40-character Git tree SHA."
  type        = string
  validation {
    condition     = can(regex("^[a-f0-9]{40}$", var.release_tree_sha))
    error_message = "release_tree_sha must be an exact lowercase 40-character Git tree SHA."
  }
}

variable "resource_manifest_sha256" {
  description = "Canonical digest of the exact approved resource manifest."
  type        = string
  validation {
    condition     = can(regex("^[a-f0-9]{64}$", var.resource_manifest_sha256))
    error_message = "resource_manifest_sha256 must be a lowercase SHA-256 digest."
  }
}

variable "operator_invoker_members" {
  description = "Explicit IAM members allowed to invoke the private operator service after deployment."
  type        = set(string)
  default     = []
  validation {
    condition = alltrue([
      for member in var.operator_invoker_members :
      member != "allUsers" && member != "allAuthenticatedUsers"
    ])
    error_message = "Public Cloud Run invoker members are prohibited."
  }
}

variable "judge_invoker_members" {
  description = "Explicit IAM members allowed to invoke the private judge service after publication review."
  type        = set(string)
  default     = []
  validation {
    condition = alltrue([
      for member in var.judge_invoker_members :
      member != "allUsers" && member != "allAuthenticatedUsers"
    ])
    error_message = "Public judge invoker members are prohibited."
  }
}

variable "exact_secret_version_refs" {
  description = "Purpose-to-exact regional Secret Manager version references. Never secret values."
  type        = map(string)
  default     = {}
  validation {
    condition = alltrue([
      for reference in values(var.exact_secret_version_refs) :
      can(regex("^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/northamerica-northeast1/secrets/[A-Za-z0-9_-]{1,255}/versions/[1-9][0-9]*$", reference))
    ])
    error_message = "Every secret reference must use an exact numeric version in regional Montréal Secret Manager."
  }
}

variable "database_tier" {
  description = "Reviewed Cloud SQL tier. Pricing must be quoted before authorization."
  type        = string
  default     = "db-custom-1-3840"
}

variable "database_disk_gb" {
  description = "Initial Cloud SQL SSD capacity."
  type        = number
  default     = 20
  validation {
    condition     = var.database_disk_gb >= 10 && var.database_disk_gb <= 100
    error_message = "database_disk_gb must be between 10 and 100 for bounded staging."
  }
}

variable "evidence_retention_days" {
  type    = number
  default = 90
  validation {
    condition     = var.evidence_retention_days >= 30 && var.evidence_retention_days <= 365
    error_message = "Evidence retention must be between 30 and 365 days."
  }
}

variable "log_retention_days" {
  type    = number
  default = 30
  validation {
    condition     = var.log_retention_days >= 1 && var.log_retention_days <= 365
    error_message = "Log retention must be between 1 and 365 days."
  }
}
