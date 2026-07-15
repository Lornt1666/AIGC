# Provider-Free Terraform Evidence Root

This standalone Terraform root validates the AIGC GCP Terraform source tree without configuring a cloud provider or creating resources.

## Commands

```bash
terraform -chdir=infra/terraform/gcp/evidence_only fmt -check -recursive
terraform -chdir=infra/terraform/gcp/evidence_only init -backend=false -input=false
terraform -chdir=infra/terraform/gcp/evidence_only validate
terraform -chdir=infra/terraform/gcp/evidence_only plan \
  -input=false \
  -lock=false \
  -refresh=false \
  -var-file=evidence.tfvars.example \
  -out=/tmp/aigc-evidence-contract.tfplan
terraform -chdir=infra/terraform/gcp/evidence_only show -json \
  /tmp/aigc-evidence-contract.tfplan
```

## Evidence produced

The planned output records:

- exact source revision;
- optional operator-supplied PR number;
- branch name;
- clean-repository assertion;
- recursive SHA-256 fingerprint of all canonical GCP Terraform `.tf` files;
- committed provider lockfile presence and SHA-256 digest;
- zero resource changes;
- no hosted-CI replacement;
- required operator review;
- no provider action;
- no Terraform apply;
- no external action.

## Boundary

This root contains no provider configuration and no resource or data blocks. A plan validates evidence assertions and output structure only. It does not contact Google Cloud, create infrastructure, access secrets, close a readiness blocker, authorize a merge, or substitute for hosted CI.
