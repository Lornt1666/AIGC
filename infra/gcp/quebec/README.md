# AIGC Québec Google Cloud Foundation

**Status:** PLAN-ONLY FOUNDATION — NO CLOUD RESOURCE CREATION OR DEPLOYMENT IS AUTHORIZED BY THIS DIRECTORY.

This Terraform root prepares the managed Google Cloud foundation for AIGC staging in Montréal, Québec (`northamerica-northeast1`). It is separate from the Gemini release candidate and deliberately cannot deploy a live model call, public service, production environment, or cross-region disaster-recovery copy.

## Trust boundary

- Codex, ChatGPT, and GitHub are repository-control and evidence-review planes. Their physical processing region is not represented as Canadian.
- Google Cloud Montréal is the intended execution and data plane.
- The owner laptop and phone are access devices only; no runtime database, raw cloud secret, or service-account key belongs on them.

## Default-deny controls

```text
resource_creation_authorized=false
staging_deployment_authorized=false
production_activation_authorized=false
public_access_authorized=false
live_model_call_authorized=false
cross_region_replication_authorized=false
service_account_key_creation_authorized=false
```

Terraform creates nothing unless an exact, validated authorization packet sets `resource_creation_authorized=true`. Cloud Run deployment remains outside this root and must use the admitted exact release SHA, tree, CI receipt and immutable image digest through the release-closure procedure based on PR #181. This root prepares foundational resources only.

## Required external identifiers

Before `terraform plan`, provide a private, untracked `terraform.tfvars` containing:

- exact Google Cloud project ID and project number;
- exact billing account ID;
- verified billing-account currency `CAD`—Google's Budget API requires the budget currency to match the billing account;
- owner-approved monthly CAD ceiling;
- admitted release SHA and tree SHA;
- exact resource-manifest SHA-256;
- approved identity members;
- exact regional Secret Manager version references, never secret values.

A non-CAD or unverified billing account fails closed. Never commit `terraform.tfvars`, Terraform state, provider credentials, billing-account identifiers, or approved authorization packets.

## Validation

```bash
python scripts/validate_quebec_cloud_authorization.py \
  --contract /secure/path/quebec-staging-authorization.json \
  --gate plan

terraform fmt -check -recursive infra/gcp/quebec
terraform -chdir=infra/gcp/quebec init -backend=false -lockfile=readonly
terraform -chdir=infra/gcp/quebec validate -json
terraform -chdir=infra/gcp/quebec test -test-directory=ci/tftest -filter=ci/tftest/inert_authority.tftest.hcl -json -verbose
```

The plan-only test uses Terraform's isolated in-memory test state and emits a
machine-readable `test_plan`. CI must not run a standalone plan after
`init -backend=false`: this production root declares a GCS backend, and a
standalone plan would require that backend to be initialized.

## Deployment sequence

1. Obtain fresh exact-head CI evidence for the release-closure branch based on PR #181 head `18e886d48c57b85d8ab8115a6fb765fa6e655fc9`.
2. Require the committed Terraform provider lockfile and native Québec validation stage to pass.
3. Complete the Québec authorization packet.
4. Apply only the foundational staging resources.
5. Inspect and retain regional provider receipts.
6. Build in Montréal from the admitted release SHA.
7. Deploy private operator and judge candidates by immutable digest with no public access and no live model call.
8. Run non-generative readiness checks.
9. Request a separate one-use Gemini canary authorization.

## Disaster recovery

The default is strict Québec operation with no Toronto copy. RPO 15 minutes and RTO 4 hours remain proposed operational targets until a restore test proves them. Toronto (`northamerica-northeast2`) disaster recovery requires a separate cross-region privacy and owner authorization packet.
