output "evidence_contract" {
  description = "Provider-free Terraform evidence contract."
  value       = module.evidence_contract.evidence_contract
}

output "evidence_source_files" {
  description = "Canonical Terraform source files included in the evidence fingerprint."
  value       = local.terraform_source_files
}
