# Terraform Inert Evidence Contract

## Status

```text
IMPLEMENTED_INTERNAL_PROVIDER_FREE_NO_RESOURCES
```

This evidence surface enriches Terraform plan artifacts without configuring Google Cloud, reading credentials, creating resources, applying state changes, or performing an external action.

## Directory structure

```text
infra/terraform/gcp/
├── evidence_only/
│   ├── evidence.tfvars.example
│   ├── main.tf
│   ├── outputs.tf
│   ├── README.md
│   ├── variables.tf
│   └── versions.tf
└── modules/
    └── evidence_contract/
        ├── main.tf
        ├── outputs.tf
        ├── README.md
        └── variables.tf
```

## Evidence contract

The module emits:

```text
contract_id
contract_version
source_revision
expected_pr_number
branch_name
repository_clean
terraform_source_fingerprint
provider_lock_present
provider_lock_sha256
resource_change_count
evidence_contract_safe
hosted_ci_replacement
operator_review_required
provider_action_performed
terraform_apply_performed
external_action_performed
```

The contract is safe only when:

```text
repository_clean = true
provider_lock_present = true
resource_change_count = 0
hosted_ci_replacement = false
operator_review_required = true
provider_action_performed = false
terraform_apply_performed = false
external_action_performed = false
```

Terraform `check` blocks reject any incompatible assertion.

## Fingerprints

The standalone evidence root computes:

- a recursive SHA-256 fingerprint of every canonical `.tf` file under `infra/terraform/gcp`;
- the SHA-256 digest of the committed `.terraform.lock.hcl`;
- the exact source revision supplied to the plan;
- an optional operator-supplied pull-request number.

Downloaded `.terraform` module directories are excluded from the source fingerprint.

## Validation commands

```bash
terraform -chdir=infra/terraform/gcp/evidence_only fmt -check -recursive
terraform -chdir=infra/terraform/gcp/evidence_only init -backend=false -input=false
terraform -chdir=infra/terraform/gcp/evidence_only validate
terraform -chdir=infra/terraform/gcp/evidence_only plan \
  -input=false \
  -lock=false \
  -refresh=false \
  -var-file=evidence.tfvars.example \
  -var="source_revision=<EXACT_REVISION>" \
  -out=/tmp/aigc-terraform-evidence-contract.tfplan
terraform -chdir=infra/terraform/gcp/evidence_only show -json \
  /tmp/aigc-terraform-evidence-contract.tfplan
```

## CI behavior

The hardened AIGC workflow:

1. formats, initializes, validates, and plans the provider-free evidence root;
2. asserts that `resource_changes` is empty;
3. verifies the planned `evidence_contract` output;
4. requires the exact workflow revision;
5. requires the committed provider lockfile;
6. writes `evidence-contract-plan.json` and `evidence-contract-summary.json` into the mandatory Terraform evidence artifact.

## Non-scope

This train does not:

- configure a Google provider;
- request OIDC authority;
- access Application Default Credentials;
- read Secret Manager;
- create a network, database, service account, budget, or cloud resource;
- run Terraform apply;
- alter the production-readiness ledger;
- replace hosted GitHub Actions evidence;
- authorize a merge;
- perform an external action.

## Admission order

This is a stacked draft above PR #123. It must not merge before PR #123 is separately admitted with successful hosted-CI evidence. After PR #123 is merged, this train must be reconstructed on exact `main`, revalidated, reviewed at its exact head, and separately disposed by the accountable operator.
