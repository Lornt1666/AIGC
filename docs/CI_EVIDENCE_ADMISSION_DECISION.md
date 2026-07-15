# CI Evidence Admission Decision

## Decision

The proposed fallback CI workflow and duplicate readiness ledger are not admitted.

## Reasons

### Fallback workflow

The proposed workflow is incompatible with the canonical repository because it:

- targets `.github/workflows/ci.yml` instead of the active `.github/workflows/aigc-ci.yml`;
- calls nonexistent `app.simulation` and `app.readiness` modules;
- uses nonexistent `terraform/staging` rather than `infra/terraform/gcp`;
- masks failed tests and Terraform commands with `|| true`;
- fabricates placeholder evidence when commands fail;
- requests `id-token: write` despite performing no WIF authentication;
- permits missing evidence with warning-only uploads;
- does not assert that the inert Terraform plan contains zero resource changes.

The active PR #123 workflow already uses immutable action identities, read-only permissions, disabled checkout credential persistence, Terraform 1.10.5, the locked Google provider, canonical repository commands, fail-closed artifact uploads, and a zero-resource Terraform assertion.

### Duplicate readiness ledger

The proposed `app/readiness/ledger.py` is not admitted because it would create a second readiness authority outside:

```text
config/production_readiness_ledger.json
src/core/production_readiness_ledger.py
```

It also:

- hard-codes a stale main revision;
- promotes work acquisition without new evidence acceptance;
- uses a different capability taxonomy and weighting model;
- omits evidence-path validation and automatic status downgrades;
- cannot replace the canonical blocker logic;
- calculates approximately 68.39 from its own supplied weights and multipliers, not 74.50.

## Accepted replacement

PR #123 adds:

```text
scripts/generate-evidence.sh
docs/LOCAL_CI_EVIDENCE_BUNDLE.md
tests/test_local_ci_evidence_generator.py
```

The generator runs canonical repository commands and fails closed. It creates supplemental local evidence only and explicitly cannot replace a successful hosted GitHub Actions run.

## Authority boundary

```text
hosted_ci_replacement: false
operator_review_required: true
merge_authorized: false
provider_action_performed: false
terraform_apply_performed: false
external_action_performed: false
```
