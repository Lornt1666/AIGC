output "deployment_baseline" {
  value = {
    environment                         = var.environment
    authorization_mode                  = local.authorization_mode
    project_id_bound                    = local.project_bound
    exact_revision_bound                = local.exact_revision_bound
    image_digest_bound                  = local.image_digest_bound
    production_release_gate_bound       = local.production_gate_bound
    staging_plan_authorization_supplied = local.staging_plan_authorization_supplied
    staging_plan_gate_bound             = local.staging_plan_gate_bound
    release_gate_bound                  = local.gate_bound
    release_permitted                   = local.release_permitted
    resource_creation_requested         = var.resource_creation_authorized
    resource_creation_effective         = local.resource_creation_effective
    unresolved_inputs                   = local.unresolved_inputs
    topology                            = local.topology
    external_action_performed           = false
  }
}
