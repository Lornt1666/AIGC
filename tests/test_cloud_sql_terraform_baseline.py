from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = ROOT / "infra" / "terraform" / "gcp"
MODULE_ROOT = TERRAFORM_ROOT / "modules" / "cloud_sql"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def terraform_module_text() -> str:
    return "\n".join(read(path) for path in sorted(MODULE_ROOT.glob("*.tf")))


def test_cloud_sql_root_module_is_three_way_fail_closed() -> None:
    main = read(TERRAFORM_ROOT / "main.tf")
    variables = read(TERRAFORM_ROOT / "cloud_sql_variables.tf")

    assert 'module "cloud_sql_staging"' in main
    assert "local.resource_creation_effective" in main
    assert 'var.environment == "staging"' in main
    assert "var.cloud_sql_enabled" in main
    assert 'variable "cloud_sql_enabled"' in variables
    assert "default     = false" in variables


def test_cloud_sql_uses_private_services_access_and_no_public_ipv4() -> None:
    module = read(MODULE_ROOT / "main.tf")

    required_resources = (
        'resource "google_compute_network" "cloud_sql"',
        'resource "google_compute_global_address" "private_service_range"',
        'resource "google_service_networking_connection" "private_vpc_connection"',
        'resource "google_sql_database_instance" "postgres"',
        'resource "google_sql_database" "application"',
    )
    for resource in required_resources:
        assert resource in module

    assert 'service                 = "servicenetworking.googleapis.com"' in module
    assert "ipv4_enabled" in module
    assert "= false" in module
    assert "private_network" in module
    assert "allocated_ip_range" in module
    assert "ssl_mode" in module


def test_cloud_sql_enables_recovery_controls_without_creating_credentials() -> None:
    module = read(MODULE_ROOT / "main.tf")
    terraform = terraform_module_text()

    assert "backup_configuration" in module
    assert "point_in_time_recovery_enabled = true" in module
    assert "transaction_log_retention_days" in module
    assert "backup_retention_settings" in module
    assert "deletion_protection = var.deletion_protection" in module
    assert "deletion_protection_enabled = var.deletion_protection" in module
    assert "ignore_changes = [settings[0].disk_size]" in module
    assert 'resource "google_sql_user"' not in terraform
    assert "root_password" not in terraform
    assert "password =" not in terraform
    assert "secret_data" not in terraform


def test_postgres_16_shared_core_tier_has_explicit_enterprise_edition() -> None:
    module = read(MODULE_ROOT / "main.tf")
    module_edition = read(MODULE_ROOT / "edition.tf")
    root = read(TERRAFORM_ROOT / "main.tf")
    root_edition = read(TERRAFORM_ROOT / "cloud_sql_edition.tf")
    example = read(TERRAFORM_ROOT / "staging.tfvars.example")

    assert "edition                     = var.edition" in module
    assert 'default     = "ENTERPRISE"' in module_edition
    assert "edition                       = var.cloud_sql_edition" in root
    assert 'default     = "ENTERPRISE"' in root_edition
    assert 'cloud_sql_edition                             = "ENTERPRISE"' in example


def test_cloud_sql_runtime_iam_is_optional_and_least_privilege() -> None:
    module = read(MODULE_ROOT / "main.tf")

    assert '"roles/cloudsql.client"' in module
    assert '"roles/cloudsql.instanceUser"' in module
    assert '"roles/run.admin"' not in module
    assert '"roles/secretmanager.secretAccessor"' not in module
    assert 'runtime_service_account_email == "" ? toset([])' in module


def test_committed_staging_example_cannot_create_resources() -> None:
    example = read(TERRAFORM_ROOT / "staging.tfvars.example")
    compact = "".join(example.split())

    assert "deployment_authorized=false" in compact
    assert "resource_creation_authorized=false" in compact
    assert "cloud_sql_enabled=false" in compact
    assert 'release_gate_result="DENY"' in compact
    assert 'cloud_sql_runtime_service_account_email=""' in compact


def test_required_cloud_sql_apis_are_explicit() -> None:
    module = read(MODULE_ROOT / "main.tf")

    for service in (
        "compute.googleapis.com",
        "servicenetworking.googleapis.com",
        "sqladmin.googleapis.com",
    ):
        assert service in module
