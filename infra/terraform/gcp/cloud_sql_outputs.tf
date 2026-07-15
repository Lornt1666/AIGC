output "cloud_sql_staging" {
  description = "Truth-preserving Cloud SQL staging module state."
  value = {
    enabled                       = var.cloud_sql_enabled
    instantiated                  = length(module.cloud_sql_staging) == 1
    instance_name                 = try(module.cloud_sql_staging[0].instance_name, null)
    connection_name               = try(module.cloud_sql_staging[0].connection_name, null)
    private_ip_address            = try(module.cloud_sql_staging[0].private_ip_address, null)
    database_name                 = try(module.cloud_sql_staging[0].database_name, null)
    network_id                    = try(module.cloud_sql_staging[0].network_id, null)
    private_service_range_name    = try(module.cloud_sql_staging[0].private_service_range_name, null)
    runtime_roles                 = try(module.cloud_sql_staging[0].runtime_roles, [])
    public_ipv4_enabled           = false
    password_or_sql_user_created  = false
    resource_creation_effective   = local.resource_creation_effective
    operator_review_required      = true
    external_action_performed     = false
  }
}
