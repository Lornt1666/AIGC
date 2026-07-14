variable "environment" {
  type        = string
  description = "Isolated staging or production environment."
  default     = "staging"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production"
  }
}

variable "project_id" {
  type      = string
  default   = ""
  nullable  = false
  sensitive = false
}

variable "primary_region" {
  type    = string
  default = "northamerica-northeast2"
}

variable "recovery_region" {
  type    = string
  default = "northamerica-northeast1"
}

variable "production_domain" {
  type    = string
  default = ""
}

variable "exact_revision" {
  type    = string
  default = ""
}

variable "image_digest" {
  type    = string
  default = ""
}

variable "release_gate_receipt_id" {
  type    = string
  default = ""
}

variable "release_gate_result" {
  type    = string
  default = "DENY"
  validation {
    condition     = contains(["PERMIT", "DENY"], var.release_gate_result)
    error_message = "release_gate_result must be PERMIT or DENY"
  }
}

variable "deployment_authorized" {
  type    = bool
  default = false
}

variable "resource_creation_authorized" {
  type        = bool
  default     = false
  description = "Must remain false until a separately approved staging or production action."
}

variable "monthly_budget_cad" {
  type    = number
  default = 200
  validation {
    condition     = var.monthly_budget_cad > 0 && var.monthly_budget_cad <= 200
    error_message = "monthly_budget_cad must be within the accepted CAD 200 ceiling"
  }
}
