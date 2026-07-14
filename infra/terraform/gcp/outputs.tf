output "deployment_baseline" {
  value = {
    environment                 = var.environment
    project_id_bound            = local.project_bound
    exact_revision_bound        = local.exact_revision_bound
    image_digest_bound          = local.image_digest_bound
    release_gate_bound          = local.gate_bound
    release_permitted           = local.release_permitted
    resource_creation_requested = var.resource_creation_authorized
    resource_creation_effective = local.resource_creation_effective
    unresolved_inputs           = local.unresolved_inputs
    topology                    = local.topology
    external_action_performed   = false
  }
}
