# CI Evidence Admission Decision

## Current decision

The proposed fallback CI workflow and duplicate readiness ledger are not admitted.

PR #123 remains the only CI-hardening train. It must remain draft and unmerged until a main-targeted GitHub-hosted workflow executes real steps and produces the mandatory simulation, Terraform, test, and readiness artifacts.

## Historical blocker and current admission rule

Earlier zero-step GitHub Actions failures were consistent with a runner-allocation or account-level restriction. Subsequent AIGC workflows have successfully executed real validation steps and produced canonical artifacts, so the older failure signature must not be treated as proof that hosted CI is still blocked. PR #123 is stale relative to current `main` and must be reconstructed against the current canonical workflow before its results can be considered.

Observed failure class:

```text
workflow accepted
job queued or created
job completed / failure
steps: none
logs: none
artifacts: none
checkout_started: false
```

This failure occurs before repository code executes. It is not evidence that the workflow, tests, Terraform, contracts, redaction scanner, or application code failed.

If a future run again fails before any step, inspect its run-level annotation and current account/organization settings. Do not infer an ongoing billing block solely from the historical runs.

## Rejected fallback workflow

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

## Rejected duplicate readiness ledger

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

## Accepted supplemental local evidence path

PR #123 contains:

```text
scripts/generate-evidence.sh
scripts/verify_evidence_manifest.py
docs/LOCAL_CI_EVIDENCE_BUNDLE.md
tests/test_local_ci_evidence_generator.py
```

The generator:

- requires a clean working tree;
- binds the exact Git revision;
- may enforce `AIGC_EXPECTED_REVISION` and record `AIGC_EXPECTED_PR_NUMBER`;
- records repository-state cleanliness proof;
- runs canonical contract, AEC-001, redaction, mock-discovery, Terraform, pytest, and readiness surfaces;
- asserts the Terraform plan contains zero resource changes;
- hashes every substantive bundle artifact;
- verifies the manifest independently;
- fails closed on every error.

Local output is supplemental only. It does not replace hosted CI and does not close issue #124.

## Local execution

From a clean checkout of the exact PR #123 head:

```bash
export AIGC_EXPECTED_PR_NUMBER=123
export AIGC_EXPECTED_REVISION=<EXACT_PR_123_HEAD>
bash scripts/generate-evidence.sh
```

The generated bundle and adjacent verification receipt may be attached to issue #124 for diagnosis and technical review.

## Issue #124 attachment comment template

Use this template only after the local command completes successfully and the files are actually attached:

```markdown
## Supplemental local evidence attached

Exact PR: #123  
Exact source revision: `<REVISION>`  
Bundle path: `<LOCAL_BUNDLE_PATH>`  
Manifest verification receipt: `<VERIFICATION_RECEIPT>`

Attached supplemental evidence includes:

- contract and AEC-001 validation logs;
- redaction scan;
- mock-only provider-discovery artifacts;
- Terraform fmt/init/validate logs;
- zero-resource inert Terraform plan and summary;
- complete pytest log;
- canonical production-readiness artifacts;
- repository-state proof;
- SHA-256 evidence manifest and verification receipt.

This evidence was generated locally because GitHub-hosted runner allocation remains blocked at the account or organization level.

```text
hosted_ci_replacement: false
operator_review_required: true
merge_authorized: false
provider_action_performed: false
terraform_apply_performed: false
external_action_performed: false
```

Issue #124 remains open. PR #123 remains draft and unmerged until a main-targeted hosted workflow executes real steps and produces the mandatory GitHub Actions artifacts.
```

## Required admission sequence

```text
correct GitHub billing / Actions budget / runner policy
-> hosted PR #123 workflow executes checkout and all steps
-> mandatory artifacts are present and exact-head bound
-> exact-head technical review
-> separate accountable-operator disposition
-> merge PR #123 only if approved
-> exact-main verification
-> reconstruct PR #121
-> exact-main verification
-> reconstruct PR #122
```

## Authority boundary

```text
hosted_ci_replacement: false
operator_review_required: true
merge_authorized: false
provider_action_performed: false
terraform_apply_performed: false
external_action_performed: false
```
