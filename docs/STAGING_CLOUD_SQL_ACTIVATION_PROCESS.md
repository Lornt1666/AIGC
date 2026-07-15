# AIGC Cloud SQL Staging Activation Process

## Decision

Cloud SQL staging must not reuse the production release gate.

The production release gate requires production readiness, no production blockers, production evidence groups, and a production release environment. Staging instead uses two separate exact-revision controls:

1. a staging infrastructure **plan authorization** that permits Terraform to render the reviewed Cloud SQL resource graph;
2. a staging infrastructure **apply authorization** that binds one exact saved plan digest and expires after a short period.

Authorization is not evidence of execution. Apply authorization is not a post-apply receipt.

## Required sequence

```text
provider discovery accepted
-> exact staging project resolved
-> WIF or accountable operator identity established
-> staging plan authorization issued
-> Terraform initialization and validation
-> saved plan generated
-> saved plan digest recorded
-> accountable review of the exact plan
-> single-use apply authorization issued
-> exact saved plan applied
-> post-apply evidence collected
-> migration, backup, restore, and connection tests
-> readiness ledger reconsidered
```

## The three Terraform conditions

For Cloud SQL to appear in an authorized staging plan, all three root conditions must be true:

```text
local.resource_creation_effective
AND var.environment == "staging"
AND var.cloud_sql_enabled
```

For staging, `local.resource_creation_effective` is derived from a valid staging infrastructure plan-authorization receipt rather than a production release-gate receipt.

## Plan command

The activation tooling writes an ephemeral auto-tfvars file after validating the plan authorization:

```bash
python scripts/prepare_staging_cloud_sql_plan.py \
  --authorization artifacts/staging/plan-authorization.json \
  --output-dir artifacts/staging/cloud-sql-plan

cd infra/terraform/gcp
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
terraform plan \
  -var-file=../../../artifacts/staging/cloud-sql-plan/activation.auto.tfvars.json \
  -out=../../../artifacts/staging/cloud-sql-plan/cloud-sql.tfplan
terraform show -json ../../../artifacts/staging/cloud-sql-plan/cloud-sql.tfplan \
  > ../../../artifacts/staging/cloud-sql-plan/cloud-sql.plan.json
```

The saved plan must be reviewed before any apply authorization is issued.

## Apply command

The apply wrapper validates that the single-use apply receipt binds the exact revision, project, Terraform fingerprint, saved-plan digest, and Cloud SQL component:

```bash
python scripts/apply_staging_cloud_sql_plan.py \
  --authorization artifacts/staging/apply-authorization.json \
  --plan artifacts/staging/cloud-sql-plan/cloud-sql.tfplan \
  --execute
```

Without `--execute`, the wrapper performs validation only and does not invoke Terraform.

## External prerequisites

Before a provider-backed plan or apply:

- a real isolated Google Cloud staging project must exist;
- billing must be enabled;
- the project ID must be confirmed by accepted discovery evidence;
- the applying identity must have only the required project, network, Service Networking, Cloud SQL, and narrowly scoped IAM permissions;
- Workload Identity Federation or an accountable interactive identity must be configured;
- Terraform must be installed;
- the Google provider must initialize successfully;
- remote Terraform state must be separately bootstrapped and verified before shared use.

## Evidence after apply

A successful Terraform exit code is insufficient. Collect:

- applied revision and plan digest;
- Cloud SQL instance and database references;
- private-IP and public-IP-disabled observations;
- IAM binding observations;
- migration result;
- connection-pool and transaction-isolation tests;
- backup creation and integrity evidence;
- isolated restore test and measured RPO/RTO;
- cost and budget evidence;
- rollback instructions and receipt.

`transactional_persistence` remains incomplete until the operational evidence is accepted.
