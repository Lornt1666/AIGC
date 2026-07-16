# GitHub Actions Account Remediation Procurement

## Purpose

This runbook coordinates the next admissible action for AIGC issue #124 without weakening PR #123, replacing hosted CI, authorizing merge, or exposing billing data.

The repository cannot modify GitHub account billing, Actions budgets, payment methods, included-minutes allocation, organization policy, or hosted-runner policy. The accountable operator performs that action in GitHub. The repository records and verifies the result through contract-bound receipts.

## Bound candidate

```text
repository: Lornt1666/AIGC
issue: #124
pull_request: #123
expected_head: 8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0
base: main
operator_review_required: true
hosted_ci_replacement: false
merge_authorized: false
terraform_apply_authorized: false
external_action_performed: false
```

If PR #123 changes head, stop. Rebind the process to the new exact head before producing any receipt.

## Procurement state machine

```text
ACCOUNT_RESTRICTION_OBSERVED
→ ACCOUNT_REMEDIATION_PERFORMED
→ GAR REMEDIATION RECEIPT ISSUED
→ EXACT-HEAD HOSTED RERUN REQUESTED
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

## 2. Build the GAR remediation receipt

From a clean checkout of the exact PR #123 head:

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

The builder fails if:

- the checkout does not match the exact head;
- required fields are placeholders;
- raw payment details are present;
- the attestation is altered;
- the receipt would authorize merge, apply, provider mutation, or external action.

## 3. Post the remediation attestation to issue #124

Post the non-sensitive receipt fields and attach the JSON receipt. Use this wording:

```markdown
## SIG-124 account remediation completed

Exact PR: #123  
Exact head: `8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0`  
GAR receipt: `<GAR-RECEIPT-ID>`  
Observed GitHub banner: `<ACTUAL NON-SENSITIVE BANNER>`  
Restriction category: `<CATEGORY>`  
Remediation performed: `<NON-SENSITIVE SUMMARY>`  
Remediation completed at: `<UTC OR OFFSET TIMESTAMP>`

The attached receipt contains no raw payment details or secrets.

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

## 4. Request an exact-head hosted rerun

Prefer rerunning the existing PR #123 workflow rather than pushing a trivial commit, because a new commit invalidates the bound candidate and all prior signatures.

GitHub UI:

```text
PR #123 → Checks / Actions → failed AIGC CI run → Re-run failed jobs
```

Or, after authenticating GitHub CLI:

```bash
gh run rerun <FAILED_RUN_ID> --failed --repo Lornt1666/AIGC
```

After the rerun is created, rebuild the GAR receipt with `--hosted-rerun-id <RUN_ID>` if the first receipt did not include it. A changed receipt receives a new receipt ID and digest.

## 5. Verify hosted recovery through read-only API calls

Only after the hosted run reports success:

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

- PR #123 is still open;
- the current PR head equals the expected SHA;
- the run is an `AIGC CI` pull-request run;
- the run started after the account remediation;
- the run is complete and successful;
- the run exposes an exact PR #123 head binding;
- the `validate` job contains real executed steps;
- every required workflow step completed successfully;
- the provider-discovery, Terraform, test, and readiness artifacts are present and unexpired.

The resulting GHR receipt always retains:

```text
operator_review_required: true
hosted_ci_replacement: false
merge_authorized: false
terraform_apply_authorized: false
provider_mutation_authorized: false
external_action_performed: false
```

## 6. Close issue #124 only after evidence review

Attach or reference:

- GAR remediation receipt;
- GHR hosted-recovery verification receipt;
- read-only hosted-recovery observation;
- successful workflow run ID;
- four required artifact names.

Issue #124 may close only when:

```text
account_remediation_attestation_present=true
current_pr_head_matches_expected=true
hosted_checkout_executed=true
hosted_steps_executed=true
provider_discovery_artifact_present=true
terraform_artifact_present=true
test_artifact_present=true
readiness_artifact_present=true
operator_review_completed=true
```

Closing issue #124 does not approve PR #123 and does not authorize merge.

## 7. Resume PR #123 admission

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
