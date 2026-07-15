variable "edition" {
  type        = string
  description = "Cloud SQL edition. ENTERPRISE is required for shared-core and custom staging tiers."
  default     = "ENTERPRISE"

  validation {
    condition     = contains(["ENTERPRISE", "ENTERPRISE_PLUS"], var.edition)
    error_message = "edition must be ENTERPRISE or ENTERPRISE_PLUS."
  }
}
