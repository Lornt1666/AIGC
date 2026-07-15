variable "source_revision" {
  type        = string
  description = "Exact Git revision represented by the evidence plan."

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.source_revision))
    error_message = "source_revision must be an exact lowercase 40-character Git SHA."
  }
}

variable "expected_pr_number" {
  type        = number
  description = "Optional operator-supplied pull-request number for traceability."
  default     = null

  validation {
    condition = (
      var.expected_pr_number == null ||
      (var.expected_pr_number > 0 && var.expected_pr_number == floor(var.expected_pr_number))
    )
    error_message = "expected_pr_number must be null or a positive integer."
  }
}

variable "branch_name" {
  type        = string
  description = "Checked-out branch name, or an empty value for detached HEAD."
  default     = ""
}

variable "repository_clean" {
  type        = bool
  description = "Whether the evidence producer observed a clean worktree, index, and untracked-file state."
}

variable "terraform_source_fingerprint" {
  type        = string
  description = "Recursive SHA-256 fingerprint of the canonical GCP Terraform source tree."

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.terraform_source_fingerprint))
    error_message = "terraform_source_fingerprint must be a lowercase SHA-256 digest."
  }
}

variable "provider_lock_present" {
  type        = bool
  description = "Whether the committed provider lockfile is present."
}

variable "provider_lock_sha256" {
  type        = string
  description = "SHA-256 digest of the committed Terraform provider lockfile."

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.provider_lock_sha256))
    error_message = "provider_lock_sha256 must be a lowercase SHA-256 digest."
  }
}

variable "resource_change_count" {
  type        = number
  description = "Observed Terraform resource-change count. The evidence contract requires zero."
  default     = 0

  validation {
    condition = (
      var.resource_change_count >= 0 &&
      var.resource_change_count == floor(var.resource_change_count)
    )
    error_message = "resource_change_count must be a non-negative integer."
  }
}

variable "hosted_ci_replacement" {
  type        = bool
  description = "Must remain false; local or inert evidence cannot replace hosted CI."
  default     = false
}

variable "operator_review_required" {
  type        = bool
  description = "Must remain true for all evidence-contract output."
  default     = true
}

variable "provider_action_performed" {
  type        = bool
  description = "Must remain false for the provider-free evidence contract."
  default     = false
}

variable "terraform_apply_performed" {
  type        = bool
  description = "Must remain false for this plan-only evidence surface."
  default     = false
}

variable "external_action_performed" {
  type        = bool
  description = "Must remain false for this internal evidence surface."
  default     = false
}
