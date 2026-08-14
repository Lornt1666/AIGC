# APIs needed by the foundational control plane but kept separate from the
# customer-content service list for clear review.
resource "google_project_service" "platform_control_plane" {
  for_each = local.create_resources ? toset([
    "billingbudgets.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
  ]) : toset([])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
