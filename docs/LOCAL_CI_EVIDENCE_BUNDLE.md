# Local CI Evidence Bundle

## Purpose

Use this procedure only when GitHub-hosted Actions cannot allocate a runner and the operator needs a reproducible local diagnostic bundle.

The local bundle is supplemental. It does not replace a successful main-targeted GitHub Actions run and does not satisfy issue #124 by itself.

## Run

From a clean checkout of the exact PR revision:

```bash
bash scripts/generate-evidence.sh
```

Optional explicit output directory:

```bash
bash scripts/generate-evidence.sh reports/artifacts/manual_review/pr-123
```

## Requirements

- clean Git working tree;
- exact 40-character Git revision;
- Python and installed repository dependencies;
- Terraform compatible with the repository lockfile;
- no provider credentials are required for the inert plan.

## Evidence generated

```text
provider_discovery_simulation/
terraform_validation/
test_results/
production_readiness/
logs/
evidence-context.json
evidence-manifest.json
run-status.json
```

The Terraform evidence is an offline, refresh-disabled plan generated from `infra/terraform/gcp/staging.tfvars.example`. The script fails if the plan contains any resource changes.

The readiness report is generated only through the canonical command:

```text
python src/aigc.py readiness
```

No readiness value is hard-coded or promoted.

## Failure semantics

The script uses `set -Eeuo pipefail` and exits nonzero if any required command fails. It does not use `|| true` and does not create placeholder success artifacts.

A failed run writes:

```text
result: FAILED_CLOSED
```

A completed run writes:

```text
result: COMPLETE
```

Both forms retain:

```text
hosted_ci_replacement: false
operator_review_required: true
provider_action_performed: false
terraform_apply_performed: false
external_action_performed: false
```

## Admission boundary

A local bundle may be attached to PR #123 for diagnosis and technical review. It must not be represented as hosted-CI evidence, operational Google Cloud evidence, authorization to merge, or authority to apply Terraform.
