# GitHub Actions Account Remediation Procurement

## Purpose

This runbook coordinates the next admissible action for AIGC issue #124 without weakening PR #123, replacing hosted CI, authorizing merge, or exposing billing data.

The repository cannot modify GitHub account billing, Actions budgets, payment methods, included-minutes allocation, organization policy, or hosted-runner policy. The accountable operator performs that action in GitHub. The repository records and verifies the result through contract-bound receipts.

## Bound target and tooling provenance

The remediation tools are intentionally developed in a separate stacked draft so PR #123 remains unchanged.

```text
repository: Lornt1666/AIGC
issue: #124
target_pull_request: #123
target_exact_head: 8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0
target_base: main
tooling_branch: agent/github-actions-account-remediation-v1
target_must_be_ancestor_of_tooling_revision: true
operator_review_required: true
hosted_ci_replacement: false
merge_authorized: false
terraform_apply_authorized: false
external_action_performed: false
```

The target PR head and the tooling revision are different facts:

- `exact_head` identifies the unchanged PR #123 candidate being recovered;
- `tooling_revision` identifies the reviewed stacked checkout that generated or verified the receipt;
- Git ancestry must prove the target PR #123 head is contained in the tooling revision.

If PR #123 changes head, stop. Rebind the process to the new exact target before producing any receipt.

## Procurement state machine

```text
ACCOUNT_RESTRICTION_OBSERVED
→ ACCOUNT_REMEDIATION_PERFORMED
→ GAR REMEDIATION RECEIPT ISSUED
→ EXACT-TARGET HOSTED RERUN REQUESTED
→ HOSTED RUN COMPLETES WITH REAL STEPS
→ REQUIRED ARTIFACTS OBSERVED
→ GHR RECOVERY VERIFICATION ISSUED
→ ISSUE #124 EVIDENCE REVIEW
→ ISSUE #124 CLOSED
→ PR #123 TECHNICAL REVIEW
→ SEPARATE OPERATOR DISPOSITION
```

No later state may be claimed from an earlier state.

## 1. Perform the account-side remediation

In GitHub, inspect the exact banner above the failed `validate` job, then check:

```text
Repository → Settings → Actions → General
Account → Settings → Billing and licensing → Usage
Account → Settings → Billing and licensing → Budgets and alerts
```

Correct the actual restriction, which may include:

- exhausted private-repository Actions minutes;
- a zero or insufficient Actions spending limit;
- payment-method or billing failure;
- repository or organization Actions policy;
- GitHub-hosted runner restriction.

Do not place card numbers, security codes, bank details, access tokens, or screenshots containing sensitive payment data in the repository or issue.

Retain a private screenshot or account reference and record only a non-sensitive evidence reference.

## 2. Prepare the stacked remediation-tooling checkout

Use the dedicated stacked remediation branch—not the PR #123 branch itself:

```bash
git fetch origin
git checkout agent/github-actions-account-remediation-v1
git pull --ff-only

git merge-base --is-ancestor \
  8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0 \
  HEAD
```

The ancestry command must exit `0`. The receipt builder performs the same check internally.

The tooling checkout must be clean before receipt generation:

```bash
git status --short
```

## 3. Build the GAR remediation receipt

From the clean stacked remediation-tooling branch:

```bash
python scripts/build_github_actions_account_remediation_receipt.py \
  --operator-name "Justice Gray Maciocha" \
  --observed-banner "<COPY THE ACTUAL GITHUB BANNER>" \
  --restriction-category SPENDING_LIMIT \
  --remediation-summary "<DESCRIBE THE ACTUAL NON-SENSITIVE CHANGE>" \
  --billing-ui-evidence-reference "Private GitHub billing screenshot reference GAR-001" \
  --remediation-completed-at "2026-07-16T01:00:00-06:00" \
  --exact-head 8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0 \
  --output artifacts/governance/github-actions-account-remediation.json
```

Allowed restriction categories:

```text
ACTIONS_MINUTES
SPENDING_LIMIT
BILLING_PAYMENT
ACTIONS_POLICY
RUNNER_POLICY
OTHER
```

The GAR receipt records both:

```text
exact_head: <PR #123 TARGET SHA>
tooling_revision: <CURRENT STACKED TOOLING SHA>
tooling_branch: agent/github-actions-account-remediation-v1
target_is_ancestor_of_tooling_revision: true
```

The builder fails if:

- the target head is not an ancestor of the tooling revision;
- required fields are placeholders;
- raw payment details are present;
- the attestation is altered;
- the receipt would authorize merge, apply, provider mutation, or external action.

## 4. Post the remediation attestation to issue #124

Post the non-sensitive receipt fields and attach the JSON receipt. Use this wording:

```markdown
## SIG-124 account remediation completed

Exact target PR: #123  
Exact target head: `8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0`  
Tooling revision: `<STACKED TOOLING SHA>`  
Tooling branch: `agent/github-actions-account-remediation-v1`  
GAR receipt: `<GAR-RECEIPT-ID>`  
Observed GitHub banner: `<ACTUAL NON-SENSITIVE BANNER>`  
Restriction category: `<CATEGORY>`  
Remediation performed: `<NON-SENSITIVE SUMMARY>`  
Remediation completed at: `<UTC OR OFFSET TIMESTAMP>`

The attached receipt contains no raw payment details or secrets. Git ancestry confirms the exact PR #123 target head is contained in the tooling revision.

```text
operator_review_required: true
hosted_ci_replacement: false
merge_authorized: false
terraform_apply_authorized: false
provider_mutation_authorized: false
external_action_performed: false
```

Issue #124 remains open pending successful exact-head hosted execution and required artifacts.
```

## 5. Request an exact-head hosted rerun

Prefer rerunning the existing PR #123 workflow rather than pushing a trivial commit, because a new PR #123 commit invalidates the bound target and all prior signatures.

GitHub UI:

```text
PR #123 → Checks / Actions → failed AIGC CI run → Re-run failed jobs
```

Or, after authenticating GitHub CLI:

```bash
gh run rerun <FAILED_RUN_ID> --failed --repo Lornt1666/AIGC
```

After the rerun is created, rebuild the GAR receipt with `--hosted-rerun-id <RUN_ID>` if the first receipt did not include it. A changed receipt receives a new receipt ID and digest.

## 6. Verify hosted recovery through read-only API calls

Remain on a clean approved remediation-tooling branch. Only after the hosted run reports success:

```bash
python scripts/verify_github_actions_hosted_recovery.py \
  --repository Lornt1666/AIGC \
  --pr-number 123 \
  --expected-head 8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0 \
  --remediation-receipt artifacts/governance/github-actions-account-remediation.json \
  --run-id <SUCCESSFUL_RUN_ID> \
  --output artifacts/governance/github-actions-hosted-recovery-verification.json \
  --observation-output artifacts/governance/github-actions-hosted-recovery-observation.json
```

The verifier uses only read-only `gh api --method GET` calls. It requires:

- the target PR #123 head is an ancestor of the verification tooling revision;
- PR #123 is still open;
- the current PR head equals the expected target SHA;
- the run ID matches the GAR-signed rerun ID when one was recorded;
- the run is an `AIGC CI` pull-request run;
- the run started after the account remediation;
- the run is complete and successful;
- the run exposes an exact PR #123 head binding;
- the `validate` job contains real executed steps;
- every required workflow step completed successfully;
- the provider-discovery, Terraform, test, and readiness artifacts are present and unexpired.

The GHR receipt records:

```text
exact_head: <PR #123 TARGET SHA>
verification_tooling_revision: <CURRENT STACKED TOOLING SHA>
verification_tooling_branch: agent/github-actions-account-remediation-v1
target_is_ancestor_of_verification_tooling_revision: true
```

It always retains:

```text
operator_review_required: true
hosted_ci_replacement: false
merge_authorized: false
terraform_apply_authorized: false
provider_mutation_authorized: false
external_action_performed: false
```

## 7. Close issue #124 only after evidence review

Attach or reference:

- GAR remediation receipt;
- GHR hosted-recovery verification receipt;
- read-only hosted-recovery observation;
- successful workflow run ID;
- four required artifact names;
- target and tooling revision ancestry proof.

Issue #124 may close only when:

```text
account_remediation_attestation_present=true
current_pr_head_matches_expected=true
target_is_ancestor_of_tooling_revision=true
hosted_checkout_executed=true
hosted_steps_executed=true
provider_discovery_artifact_present=true
terraform_artifact_present=true
test_artifact_present=true
readiness_artifact_present=true
operator_review_completed=true
```

Closing issue #124 does not approve PR #123 and does not authorize merge.

## 8. Resume PR #123 admission

After issue #124 closes:

```text
exact-head technical review
→ separate accountable-operator disposition
→ immediate re-fetch of main/head/check/review state
→ merge only the exact admitted head
```

Required disposition wording after all evidence has been reviewed:

```text
I, Justice Gray Maciocha, admit PR #123 at exact head 8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0 for repository merge only, after reviewing the successful hosted AIGC CI run, required evidence artifacts, GAR remediation receipt, and GHR recovery verification receipt. This disposition does not authorize Terraform apply, Google Cloud mutation, credential use, deployment, job submission, messaging, scheduling, or any other external action.
```

Do not use that wording before every prerequisite is satisfied.
