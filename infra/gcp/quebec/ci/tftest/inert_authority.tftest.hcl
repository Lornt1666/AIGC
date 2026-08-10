variables {
  project_id                              = "aigc-ci-inert-12345"
  project_number                          = "123456789012"
  billing_account_id                      = "000000-000000-000000"
  region                                  = "northamerica-northeast1"
  resource_prefix                         = "aigc-ci-inert"
  resource_creation_authorized            = false
  staging_deployment_authorized           = false
  production_activation_authorized        = false
  public_access_authorized                = false
  live_model_call_authorized              = false
  cross_region_replication_authorized     = false
  service_account_key_creation_authorized = false
  monthly_budget_cad                      = 1
  budget_notification_channels            = []
  release_sha                             = "0000000000000000000000000000000000000000"
  release_tree_sha                        = "0000000000000000000000000000000000000000"
  resource_manifest_sha256                = "0000000000000000000000000000000000000000000000000000000000000000"
  authorization_inventory_sha256          = "0000000000000000000000000000000000000000000000000000000000000000"
  operator_invoker_members                = []
  judge_invoker_members                   = []
  exact_secret_version_refs               = {}
}

run "inert_authority_boundary" {
  command = plan

  plan_options {
    refresh = false
  }

  assert {
    condition     = output.authority_state.resource_creation_authorized == false
    error_message = "The inert test must not authorize resource creation."
  }

  assert {
    condition     = output.authority_state.staging_deployment_authorized == false
    error_message = "The inert test must not authorize staging deployment."
  }

  assert {
    condition     = output.authority_state.production_activation_authorized == false
    error_message = "The inert test must not authorize production activation."
  }

  assert {
    condition     = output.regional_foundation == null
    error_message = "The inert test must not plan a regional foundation."
  }

  assert {
    condition     = output.github_workload_identity == null
    error_message = "The inert test must not plan a workload identity."
  }

  assert {
    condition     = output.regional_secret_metadata == null
    error_message = "The inert test must not plan regional secrets."
  }
}
