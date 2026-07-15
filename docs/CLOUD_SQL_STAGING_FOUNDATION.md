# AIGC Cloud SQL Staging Foundation

## Status

`IMPLEMENTED_INTERNAL_NO_PROVIDER_ACTION`

This document describes an infrastructure definition. No Google Cloud API call, project-service enablement, VPC creation, IAM change, Cloud SQL creation, database mutation, secret access, plan, apply, or external action was performed by admitting the files.

## Directory structure

```text
infra/terraform/gcp/
├── guardrails.tf
├── main.tf
├── outputs.tf
├── variables.tf
├── versions.tf
├── cloud_sql_variables.tf
├── cloud_sql_outputs.tf
├── staging.tfvars.example
└── modules/
    └── cloud_sql/
        ├── main.tf
        ├── variables.tf
        ├── outputs.tf
        └── README.md
```

## Defined staging foundation

The module defines:

- required Compute, Service Networking, and Cloud SQL Admin APIs;
- a dedicated VPC rather than the default network;
- an automatically allocated private-services range;
- a Service Networking private connection;
- one private-IP Cloud SQL PostgreSQL instance;
- automated backups and point-in-time recovery;
- encrypted transport;
- Query Insights without client-address recording;
- one application database;
- optional Cloud SQL client and instance-user IAM roles for one approved runtime service account.

No database user or password is created. Application credential material remains outside Terraform and must use approved identity and secret-management paths.

## Resource gate

The root module instantiates Cloud SQL only when:

```text
local.resource_creation_effective == true
AND environment == staging
AND cloud_sql_enabled == true
```

`local.resource_creation_effective` requires:

- resource creation authorization;
- an exact 40-character repository revision;
- an immutable SHA-256 image digest;
- a valid project ID;
- a candidate-bound release-gate receipt;
- release-gate result `PERMIT`;
- deployment authorization.

The committed example keeps all authority false.

## Offline validation

From the repository root:

```bash
terraform -chdir=infra/terraform/gcp fmt -check -recursive
terraform -chdir=infra/terraform/gcp init -backend=false
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan \
  -refresh=false \
  -var-file=staging.tfvars.example
```

With the committed example, the Cloud SQL module count is zero. The plan must not be represented as provider evidence, operational evidence, or permission to apply.

## Future authorized staging sequence

```text
provider discovery evidence accepted
→ private state backend verified
→ exact Terraform plan generated
→ plan evidence reviewed and accepted
→ exact-plan apply authorization issued
→ authorized apply
→ post-apply operational evidence accepted
→ database connection and migration evidence
→ backup and isolated-restore evidence
→ readiness reconciliation
```

## Evidence required before capability completion

The Terraform definition alone does not complete `transactional_persistence` or `production_deployment`. Required operational evidence includes:

- observed private-IP instance creation;
- verified workload identity and Secret Manager references;
- successful PostgreSQL repository-adapter connection;
- migration-lock observation;
- prior-schema upgrade test;
- concurrent transaction test;
- connection-loss retry test;
- cross-tenant and cross-project denial tests;
- automated backup integrity evidence;
- isolated restore evidence;
- measured RPO and RTO;
- rollback and destruction receipts for the isolated test environment.

## Cost boundary

The module does not claim that a budget alert is a spending cap. Machine tier, availability type, storage growth, backups, networking, logging, and query workloads must be reviewed against the staging budget before authorization.
