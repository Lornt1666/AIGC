variable "source_revision" {
  type        = string
  description = "Exact Git revision represented by this evidence plan."
  default     = "0000000000000000000000000000000000000000"

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.source_revision))
    error_message = "source_revision must be an exact lowercase 40-character Git SHA."
  }
}

variable "expected_pr_number" {
  type        = number
  description = "Optional operator-supplied pull-request number."
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
  description = "Whether the evidence producer observed a clean repository state."
  default     = true
}
