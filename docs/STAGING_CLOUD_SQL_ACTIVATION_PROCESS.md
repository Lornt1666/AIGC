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
-> verified remote Terraform state backend
-> WIF or accountable operator identity established
-> staging plan authorization issued
-> Terraform initialization and validation
-> saved plan generated against the verified backend
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

## Build the plan authorization

```bash
python scripts/build_staging_infrastructure_authorization.py plan \
  --discovery-evidence artifacts/staging/provider-discovery-evidence.json \
  --project-id YOUR_STAGING_PROJECT_ID \
  --monthly-budget-cad 50 \
  --ttl-minutes 120 \
  --operator-name "Justice Gray Maciocha" \
  --decision APPROVED \
  --output artifacts/staging/plan-authorization.json
```

## Prepare activation variables

```bash
python scripts/prepare_staging_cloud_sql_plan.py \
  --authorization artifacts/staging/plan-authorization.json \
  --discovery-evidence artifacts/staging/provider-discovery-evidence.json \
  --output-dir artifacts/staging/cloud-sql-plan
```

The command validates the exact revision, project, discovery receipt, budget, authorization lifetime, and recursive Terraform fingerprint. It writes an ephemeral `activation.auto.tfvars.json`. It does not contact Google Cloud or authorize apply.

## Initialize and create the saved plan

Offline syntax validation may use `terraform init -backend=false`, but an applyable saved plan must be created after the real remote state backend has been bootstrapped and verified.

```bash
terraform -chdir=infra/terraform/gcp fmt -check -recursive
terraform -chdir=infra/terraform/gcp init -reconfigure \
  -backend-config=PATH_TO_REVIEWED_BACKEND_CONFIG
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan \
  -var-file=../../../artifacts/staging/cloud-sql-plan/activation.auto.tfvars.json \
  -out=../../../artifacts/staging/cloud-sql-plan/cloud-sql.tfplan
terraform -chdir=infra/terraform/gcp show -json \
  ../../../artifacts/staging/cloud-sql-plan/cloud-sql.tfplan \
  > artifacts/staging/cloud-sql-plan/cloud-sql.plan.json
```

Review the saved plan and its JSON rendering before issuing apply authority.

## Build the single-use apply authorization

```bash
python scripts/build_staging_infrastructure_authorization.py apply \
  --plan-authorization artifacts/staging/plan-authorization.json \
  --saved-plan artifacts/staging/cloud-sql-plan/cloud-sql.tfplan \
  --ttl-minutes 30 \
  --operator-name "Justice Gray Maciocha" \
  --decision APPROVED \
  --output artifacts/staging/apply-authorization.json
```

## Validate or apply the exact saved plan

Validation only:

```bash
python scripts/apply_staging_cloud_sql_plan.py \
  --authorization artifacts/staging/apply-authorization.json \
  --plan-authorization artifacts/staging/plan-authorization.json \
  --plan artifacts/staging/cloud-sql-plan/cloud-sql.tfplan
```

Provider mutation:

```bash
python scripts/apply_staging_cloud_sql_plan.py \
  --authorization artifacts/staging/apply-authorization.json \
  --plan-authorization artifacts/staging/plan-authorization.json \
  --plan artifacts/staging/cloud-sql-plan/cloud-sql.tfplan \
  --execute
```

Without `--execute`, the wrapper performs validation only and does not invoke Terraform. With `--execute`, it applies only the exact saved plan whose digest is bound to the unexpired single-use receipt.

## External prerequisites

Before a provider-backed plan or apply:

- a real isolated Google Cloud staging project must exist;
- billing must be enabled;
- the project ID must be confirmed by accepted discovery evidence;
- the applying identity must have only the required project, network, Service Networking, Cloud SQL, and narrowly scoped IAM permissions;
- Workload Identity Federation or an accountable interactive identity must be configured;
- Terraform must be installed;
- the Google provider must initialize successfully;
- remote Terraform state must be separately bootstrapped and verified.

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

## Admission evidence

Repository admission requires a complete main-targeted CI run. A GitHub Actions runner failure that produces no executed steps, logs, or artifacts is infrastructure noise and must be rerun or replaced by a fresh run; it is never accepted as repository evidence.

`transactional_persistence` remains incomplete until the operational evidence is accepted.
