variable "staging_plan_authorization_path" {
  type        = string
  description = "Path to an exact-revision staging infrastructure plan-authorization receipt."
  default     = ""
}

variable "staging_terraform_fingerprint" {
  type        = string
  description = "Recursive SHA-256 fingerprint of the authorized Terraform tree."
  default     = ""

  validation {
    condition = (
      var.staging_terraform_fingerprint == "" ||
      can(regex("^[a-f0-9]{64}$", var.staging_terraform_fingerprint))
    )
    error_message = "staging_terraform_fingerprint must be empty or a lowercase SHA-256 digest."
  }
}
