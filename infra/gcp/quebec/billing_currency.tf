variable "billing_account_currency" {
  description = "Verified currency of the exact Google Cloud billing account. It must match the Budget API amount currency."
  type        = string
  default     = "CAD"

  validation {
    condition     = var.billing_account_currency == "CAD"
    error_message = "The authorized AIGC staging billing account must be denominated in CAD."
  }
}

check "billing_account_currency_matches_ceiling" {
  assert {
    condition     = var.billing_account_currency == "CAD"
    error_message = "The CAD ceiling cannot be applied to a billing account denominated in another currency."
  }
}
