output "instance_name" {
  description = "Cloud SQL instance name."
  value       = google_sql_database_instance.postgres.name
}

output "connection_name" {
  description = "Cloud SQL connection name used by Cloud SQL connectors."
  value       = google_sql_database_instance.postgres.connection_name
}

output "private_ip_address" {
  description = "Private IP address assigned to the Cloud SQL instance."
  value       = google_sql_database_instance.postgres.private_ip_address
}

output "database_name" {
  description = "Application database name."
  value       = google_sql_database.application.name
}

output "network_id" {
  description = "Dedicated private Cloud SQL VPC network ID."
  value       = google_compute_network.cloud_sql.id
}

output "private_service_range_name" {
  description = "Reserved private services access range name."
  value       = google_compute_global_address.private_service_range.name
}

output "runtime_roles" {
  description = "Optional IAM roles granted to the runtime service account."
  value       = sort(tolist(local.runtime_roles))
}
