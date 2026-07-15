locals {
  canonical_gcp_root = abspath("${path.root}/..")
  terraform_source_files = sort([
    for relative in fileset(local.canonical_gcp_root, "**/*.tf") : relative
    if !startswith(relative, ".terraform/") && !strcontains(relative, "/.terraform/")
  ])
  terraform_source_fingerprint = sha256(join("|", [
    for relative in local.terraform_source_files :
    "${relative}:${filesha256("${local.canonical_gcp_root}/${relative}")}"
  ]))
  provider_lock_path    = "${local.canonical_gcp_root}/.terraform.lock.hcl"
  provider_lock_present = fileexists(local.provider_lock_path)
  provider_lock_sha256 = (
    local.provider_lock_present ?
    filesha256(local.provider_lock_path) :
    sha256("")
  )
}

module "evidence_contract" {
  source = "../modules/evidence_contract"

  source_revision              = var.source_revision
  expected_pr_number           = var.expected_pr_number
  branch_name                  = var.branch_name
  repository_clean             = var.repository_clean
  terraform_source_fingerprint = local.terraform_source_fingerprint
  provider_lock_present        = local.provider_lock_present
  provider_lock_sha256         = local.provider_lock_sha256
  resource_change_count        = 0
  hosted_ci_replacement        = false
  operator_review_required     = true
  provider_action_performed    = false
  terraform_apply_performed    = false
  external_action_performed    = false
}
