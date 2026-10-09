# Local CI Evidence Bundle

## Purpose

Use this procedure only when GitHub-hosted Actions cannot allocate a runner and the operator needs a reproducible local diagnostic bundle.

The local bundle is supplemental. It does not replace a successful main-targeted GitHub Actions run and does not satisfy issue #124 by itself.

## Exact PR-head run

From a clean checkout of the exact PR revision:

```bash
export AIGC_EXPECTED_PR_NUMBER=123
export AIGC_EXPECTED_REVISION=<EXACT_PR_123_HEAD>
bash scripts/generate-evidence.sh
```

The generator fails before producing evidence when the checked-out revision does not match `AIGC_EXPECTED_REVISION`.

Optional explicit output directory:

```bash
bash scripts/generate-evidence.sh reports/artifacts/manual_review/pr-123
```

## Requirements

- clean Git working tree;
- clean staged index;
- no untracked non-ignored files;
- exact 40-character Git revision;
- HEAD resolves to a commit object;
- Python and installed repository dependencies;
- Terraform compatible with the repository lockfile;
- no provider credentials are required for the inert plan.

## Repository-state proof

The bundle records:

```text
source_revision
branch_name
head_object_type
expected_revision
expected_pr_number
worktree_clean
index_clean
tracked_diff_clean
untracked_clean
clean_status_sha256
```

`expected_pr_number` is an operator-supplied assertion for traceability. The local script does not claim that it independently queried GitHub for PR metadata.

## Evidence generated

```text
provider_discovery_simulation/
terraform_validation/
test_results/
production_readiness/
logs/
evidence-context.json
repository-state.json
evidence-manifest.json
run-status.json
```

The generator also writes an adjacent independent verification receipt and log:

```text
<BUNDLE_PATH>.verification.json
<BUNDLE_PATH>.verification.log
```

Keeping these files adjacent prevents the verification process from changing the already-manifested bundle.

## Canonical surfaces

The generator runs:

```text
python src/aigc.py validate
python src/validate_aec_001.py
python src/security/redaction_scanner.py
python scripts/run_provider_discovery_mock.py
terraform fmt/init/validate/plan/show under infra/terraform/gcp
python -m pytest
python src/aigc.py readiness
```

The Terraform evidence is an offline, refresh-disabled plan generated from `infra/terraform/gcp/staging.tfvars.example`. The script fails if the plan contains any resource changes.

The readiness report is generated only through the canonical readiness command. No readiness value is hard-coded or promoted.

## Manifest verification

`scripts/verify_evidence_manifest.py` independently verifies:

- exact source revision;
- context and repository-state contracts;
- required artifact presence;
- artifact-count consistency;
- safe relative paths;
- duplicate-path rejection;
- prohibition of symlinks;
- SHA-256 digest and file-size consistency;
- no unexpected or missing files;
- canonical production-readiness JSON evidence;
- all no-external-action flags.

Manual verification may be repeated with:

```bash
python scripts/verify_evidence_manifest.py \
  <BUNDLE_PATH> \
  --expected-revision <EXACT_REVISION>
```

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

A local bundle may be attached to PR #123 or issue #124 for diagnosis and technical review. It must not be represented as hosted-CI evidence, operational Google Cloud evidence, authorization to merge, authority to apply Terraform, or proof that the account-level Actions restriction has been repaired.
