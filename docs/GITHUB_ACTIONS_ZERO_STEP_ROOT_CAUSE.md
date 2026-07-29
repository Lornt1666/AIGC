# GitHub Actions Zero-Step Root Cause Analysis

## Status

`ROOT_CAUSE_CLASS_ISOLATED_EXACT_ACCOUNT_CAUSE_PENDING_ANNOTATION`

The repository is not currently failing inside Python, Terraform, tests, checkout, or an action implementation. GitHub is creating a workflow run and a failed job record, but it is not allocating a runner. The result is:

```text
status: completed
conclusion: failure
steps: none
logs: none
artifacts: none
```

No repository command executes in this state.

## Decisive evidence

### Last complete successful workflow

PR #120, exact head:

```text
94086c703d1809c46cf9a0d790cd7ca289d310bb
```

Run:

```text
29426049478
```

Job:

```text
87388608275
```

This run completed checkout, Python setup, HashiCorp Terraform setup, dependency installation, contract validation, redaction scanning, procurement smoke stages, provider-discovery simulation, Terraform formatting/init/validate/plan/show, tests, readiness evaluation and all required uploads.

Therefore these surfaces were proven operational immediately before the current incident:

- `ubuntu-latest` hosted runners;
- GitHub-owned actions;
- verified third-party HashiCorp action;
- immutable HashiCorp action SHA;
- Python 3.12 setup;
- repository checkout;
- dependency installation;
- Terraform 1.10.5;
- inert Google provider plan;
- pytest;
- artifact upload.

### First observed blocked train

PR #121, exact head:

```text
bccce481fb1efae8deb52fbc41eec209620031fa
```

Run:

```text
29427396627
```

Job:

```text
87393668509
```

The job failed with zero steps and no logs. This occurred shortly after PR #120 succeeded on the same repository owner and base mainline.

### Shell-only runner probe

A temporary workflow was created containing one Bash step and no `uses:` actions. It required no checkout, no repository content and no third-party component.

Run:

```text
29556582162
```

Job:

```text
87809827885
```

Result:

```text
failed
steps: 0
logs: unavailable
```

This proves that action pinning, action allowlists, checkout, Python, Terraform and repository source code are not the primary cause.

### GitHub-owned action probe

Run:

```text
29556582122
```

Job:

```text
87809827769
```

The immutable GitHub-owned checkout probe also failed before all steps.

### Verified third-party action probe

Run:

```text
29556582153
```

Job:

```text
87809827938
```

The immutable verified HashiCorp action probe failed with the same signature.

## Tribunal conclusion

```text
classification:
HOSTED_RUNNER_NOT_ALLOCATED_ACCOUNT_OR_REPOSITORY_ELIGIBILITY_BLOCK

confidence: high
runner_allocated: false
repository_commands_executed: false
```

The exact account-side cause remains pending because GitHub exposes one job annotation in the UI, but the Actions jobs and email APIs used during this investigation do not return the annotation text.

## Ranked remaining causes

### 1. Included private-repository Actions minutes exhausted

Private repositories consume the repository owner's included or paid GitHub-hosted runner usage. GitHub documents that usage is blocked after included quota exhaustion when no valid payment method is available.

This is the strongest candidate because:

- the repository is private;
- the workflow run number is high;
- full runs had been executing repeatedly;
- a complete run succeeded shortly before all subsequent jobs stopped acquiring runners;
- even a two-second shell-only probe cannot start.

This remains a reasoned candidate, not a final factual determination, until the Usage page or annotation is observed.

### 2. User-level Actions budget or spending hard stop

GitHub user-level budgets can stop metered usage. A zero or exhausted Actions budget can block additional hosted runner use.

### 3. Missing or invalid payment method after included quota exhaustion

GitHub documents that additional use is blocked after included quota exhaustion if the account lacks a valid payment method.

### 4. Repository Actions permission restriction

Repository Actions may be disabled or restricted. The REST endpoint below reveals whether Actions is enabled and whether all, local-only, or selected actions are allowed:

```text
GET /repos/Lornt1666/AIGC/actions/permissions
```

### 5. Account or hosted-runner eligibility restriction

An account review, restriction, plan incompatibility or hosted-runner eligibility condition can prevent allocation before job setup.

### 6. Legacy per-repository plan

GitHub documents that Actions is unavailable for private repositories owned by accounts using legacy per-repository plans.

### 7. GitHub platform incident

GitHub experienced Actions runner-start incidents on July 9 and July 13, 2026. Both were marked resolved. The public Actions component was operational while the current probes continued to fail, so a current broad outage is not the leading explanation.

## Causes ruled out as the primary failure

- invalid Python implementation;
- failing pytest tests;
- Terraform syntax or validation failure;
- Terraform provider initialization failure;
- repository checkout failure;
- mutable versus immutable action references;
- HashiCorp action policy as the sole cause;
- GitHub-owned action policy as the sole cause;
- issue #128 implementation;
- PR #129 truth-procurement code;
- artifact upload configuration;
- workflow step ordering.

Those components can only fail after a runner is allocated and job setup begins.

## Exact operator inspection order

1. Open run `29556582162`.
2. Open job `acquire-runner-shell-only`.
3. Copy the exact non-sensitive annotation text.
4. Open `Repository > Settings > Actions > General`.
5. Confirm GitHub Actions is enabled.
6. Confirm standard GitHub-hosted runners are allowed.
7. Record the allowed-actions policy.
8. Open `Account > Settings > Billing and licensing > Usage`.
9. Inspect GitHub Actions minutes and storage for the current billing period.
10. Open `Budgets and alerts`.
11. Inspect user-level Actions budgets and hard-stop settings.
12. Confirm payment eligibility without recording payment identifiers.
13. Confirm the account is not using a legacy per-repository plan.

Do not post card numbers, bank information, security codes, payment identifiers, access tokens or sensitive billing screenshots.

## Read-only diagnostic collector

Run from an authenticated checkout:

```bash
python scripts/collect_github_actions_preflight.py
```

Required environment variable:

```text
GH_TOKEN
```

or:

```text
GITHUB_TOKEN
```

The token requires repository Administration read access and Actions read access. The collector performs only GET requests and never writes the token to disk or output.

It collects:

- repository state;
- repository Actions permissions;
- default workflow permissions;
- selected-actions policy where configured;
- exact workflow run;
- exact job and steps;
- artifacts;
- check-run annotations where the token/API permits;
- current GitHub public status;
- a deterministic classification.

Default output:

```text
reports/artifacts/governance/github-actions-zero-step-live-diagnosis.json
```

## Remediation branches

### If the annotation identifies minutes, budget or payment

1. Correct the account billing or budget condition.
2. Record only a non-sensitive summary and timestamp.
3. Generate the GAR receipt.
4. Rerun unchanged PR #123.
5. Require checkout, real steps, logs and all four artifact families.
6. Generate GHR verification.

### If repository Actions is disabled

1. Enable Actions for `Lornt1666/AIGC`.
2. Keep workflow permissions read-only unless a specific reviewed workflow requires more.
3. Allow GitHub-owned actions and the exact immutable verified HashiCorp action used by AIGC.
4. Rerun the shell-only probe first.
5. Rerun PR #123 only after the shell-only probe executes.

### If permissions and billing are valid but runner allocation still fails

Open a GitHub Support case containing:

```text
repository: Lornt1666/AIGC
last successful run: 29426049478
first zero-step run: 29427396627
shell-only run: 29556582162
shell-only job: 87809827885
GitHub-owned action run: 29556582122
verified third-party action run: 29556582153
signature: completed/failure, zero steps, no logs, no artifacts
current public Actions status: operational
```

Include the exact non-sensitive UI annotation and the read-only collector output. Do not include secrets or payment identifiers.

## Temporary probe lifecycle

The three probe workflows are diagnostic-only. After their run IDs and conclusions are recorded, remove them from the branch before admission so they do not create recurring checks or notification noise.

## Official references

- GitHub Actions billing and usage: <https://docs.github.com/en/actions/concepts/billing-and-usage>
- GitHub Actions billing: <https://docs.github.com/en/billing/concepts/product-billing/github-actions>
- Budgets and alerts: <https://docs.github.com/en/billing/concepts/budgets-and-alerts>
- Actions permissions REST API: <https://docs.github.com/en/rest/actions/permissions>
- GitHub-hosted runners: <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>
- Workflow run logs: <https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs>
- GitHub service status: <https://www.githubstatus.com/>

## Boundary

```text
account_remediation_performed=false
GAR_receipt_issued=false
hosted_recovery_successful=false
GHR_receipt_issued=false
merge_authorized=false
terraform_apply_authorized=false
external_action_performed=false
```
