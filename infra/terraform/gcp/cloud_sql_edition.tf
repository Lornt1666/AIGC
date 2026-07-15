variable "cloud_sql_edition" {
  type        = string
  description = "Cloud SQL edition. ENTERPRISE is the staging default for the shared-core tier."
  default     = "ENTERPRISE"

  validation {
    condition     = contains(["ENTERPRISE", "ENTERPRISE_PLUS"], var.cloud_sql_edition)
    error_message = "cloud_sql_edition must be ENTERPRISE or ENTERPRISE_PLUS."
  }
}
