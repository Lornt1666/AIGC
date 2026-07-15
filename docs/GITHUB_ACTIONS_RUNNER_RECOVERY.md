# GitHub Actions Runner Recovery

## Current failure signature

Several main-targeted AIGC workflow runs have completed with:

```text
job: validate
conclusion: failure
steps: none
logs: none
artifacts: none
```

This signature occurs before repository checkout or workflow-step execution. It is not test, Terraform, contract, redaction, or application evidence.

Affected runs currently include:

- `29427190705` — PR #121;
- `29427396627` — PR #121 fresh run and rerun;
- `29428548849` — PR #123 pinned-action workflow;
- `29428764139` — PR #123 latest exact-head run and rerun.

## Recovery checks

In the GitHub Actions UI, inspect the run-level annotation before changing code:

1. confirm Actions is enabled for the repository;
2. confirm the account or organization has available Actions minutes and no spending-limit block;
3. confirm payment and billing status for private-repository hosted runners;
4. confirm repository and organization Actions policies allow the pinned actions;
5. confirm no runner-group, concurrency, or account-level restriction prevented job assignment;
6. retry the failed run only after the account-level condition is resolved;
7. require actual steps, logs, and evidence artifacts before accepting the run.

## Supplemental local evidence

A local operator may generate a fail-closed evidence bundle while hosted-runner allocation is unavailable:

```bash
bash scripts/generate-evidence.sh
```

The generator requires:

- a clean working tree;
- an exact Git revision;
- Python;
- Terraform;
- all repository dependencies.

It runs the same canonical repository surfaces used by CI:

```text
contract validation
AEC-001 validation
redaction scan
mock-only provider discovery
Terraform fmt/init/validate
zero-resource inert Terraform plan
complete pytest suite
canonical production-readiness evaluator
SHA-256 evidence manifest
```

The script fails closed. It does not use `|| true`, invent placeholder JSON, hard-code a readiness result, run `terraform apply`, contact Google Cloud, or perform an external action.

Every local bundle states:

```text
hosted_ci_replacement: false
operator_review_required: true
provider_action_performed: false
terraform_apply_performed: false
external_action_performed: false
```

Local evidence may support diagnosis and review, but it does not satisfy the completion rule for this incident. Issue #124 remains open until a main-targeted hosted workflow executes real steps and produces the mandatory GitHub Actions artifacts.

## Admission order after recovery

```text
PR #123 — immutable CI hardening
-> exact-main verification
-> reconstruct PR #121 — staging plan/apply authorization
-> exact-main verification
-> reconstruct PR #122 — one-click cockpit and Jobs & Interviews
```

Do not merge a PR whose only current workflow result contains no executed steps or evidence artifacts.
