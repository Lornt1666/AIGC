# AIGC Current Repository Truth Procurement

## Status

`IMPLEMENTED_INTERNAL_PENDING_HOSTED_VALIDATION`

This runbook turns the repository's unresolved truth values into an ordered, evidence-backed procurement program. It does not fabricate completion, substitute authority for evidence, modify GitHub billing, merge a pull request, create cloud resources, apply Terraform, communicate with an employer, submit work, or perform any other external action.

Canonical machine-readable ledger:

```text
config/current_repository_truth_procurement.json
```

Contract:

```text
schemas/current_repository_truth_procurement.schema.json
```

Evaluator:

```text
src/core/current_repository_truth_procurement.py
```

Tests:

```text
tests/test_current_repository_truth_procurement.py
```

## Tribunal ruling: two kinds of false

A mature system must not assume every `false` value is a defect.

### Completion targets

These values are currently false but must eventually become true through real work and accepted evidence:

1. hosted validation successful;
2. issue #124 resolved;
3. PR #123 admitted and exact main verified;
4. PR #129 rebound, validated and admitted;
5. PR #121 reconstructed and admitted;
6. Cloud Run staging runtime implemented;
7. isolated Cloud SQL and Cloud Run resources created;
8. Canary A passed;
9. PR #122 reconstructed with issue #128;
10. Canary B passed;
11. one approved read-only connector proven.

### Safety invariants

These values must remain false:

- direct writes to `main`;
- self-approval;
- automatic merge;
- automatic external commitments;
- local evidence replacing hosted CI;
- raw secrets committed or logged;
- PR #129 itself claiming cloud or counterparty action;
- automatic job-application submission in the current release.

Momentum is gained by completing the first list while testing and preserving the second.

## Current next action

The first incomplete transition is:

```text
T1_HOSTED_VALIDATION_SUCCESSFUL
```

Accountable actor:

```text
GITHUB_ACCOUNT_ADMIN_AND_ACCOUNTABLE_OPERATOR
```

Required actions:

1. Inspect the actual non-sensitive banner on PR #123's failed `validate` job.
2. Correct the real Actions minutes, spending, billing, policy or runner-allocation restriction.
3. Generate a valid GAR receipt from genuine observations.
4. Rerun unchanged PR #123 exact head.
5. Require checkout, non-empty steps, passing tests and all mandatory artifact families.
6. Generate and review a valid GHR recovery receipt.

The repository connector cannot inspect or modify account billing controls. That is an actual human account-administration dependency, not a missing code feature.

## Transition program

### T1 — Hosted validation successful

Target:

```text
false → true
```

Evidence:

- actual non-sensitive restriction banner;
- GAR receipt;
- exact successful PR #123 run;
- checkout and real step execution;
- provider-discovery artifact;
- Terraform artifact;
- test artifact;
- readiness artifact;
- GHR receipt.

Stop if the PR head moves, the job again has zero steps, evidence is incomplete, or sensitive information appears.

### T2 — Issue #124 resolved

Close the incident only after attributable review of GAR, run, jobs, logs, artifacts and GHR evidence. Local-only evidence cannot close this issue.

### T3 — PR #123 admitted

Required order:

```text
exact-head technical review
→ separate accountable-operator disposition
→ expected-head-protected merge
→ exact-main verification
→ hosted mainline CI
```

### T4 — PR #129 rebound and admitted

PR #129 is currently bound to the pre-PR-#123 mainline. After main moves:

1. reconstruct or rebind it;
2. refresh every exact revision;
3. rerun both canonical validators;
4. complete hosted CI;
5. complete exact-head review;
6. record separate disposition.

### T5 — PR #121 reconstructed and admitted

Preserve separate, short-lived and exact bindings for:

- `SIP-*` plan authority;
- saved-plan digest;
- `SIA-*` apply authority;
- single-use execution;
- staging-only scope.

Do not reuse the production release gate for initial staging.

### T6 — Cloud Run runtime implemented

Internal implementation should include:

- non-root `Dockerfile`;
- `.dockerignore`;
- deterministic dependency installation;
- `/health` readiness and liveness behavior;
- Cloud Run v2 resource-gated Terraform module;
- Artifact Registry;
- runtime service account;
- Secret Manager references;
- private Cloud SQL connectivity;
- structured logs;
- immutable image digest;
- SBOM;
- provenance;
- signature;
- vulnerability report;
- deployment manifest.

All resource switches remain disabled by default.

### T7 — Isolated staging resources created

Required external sequence:

```text
dedicated staging project
→ approved billing and CAD 50 budget
→ remote state
→ WIF and least-privilege IAM
→ accepted read-only provider discovery
→ SIP plan authorization
→ provider-backed saved plan
→ accountable plan review
→ SIA apply authorization
→ exact-plan apply
→ execution receipt
```

No production project, customer data, public database access, broad IAM, stale plan or reused permit is acceptable.

### T8 — Canary A passed

Canary A proves the platform before autonomous employer-work behavior:

```text
operator authenticates
→ /health passes
→ PostgreSQL connects
→ migrations run
→ basic internal work order executes
→ governance artifacts persist
→ audit evidence persists
→ logs, metrics and alerts appear
→ budget notification arrives
→ rollback succeeds
→ isolated restore succeeds
```

Record observed RPO and RTO rather than repeating declared targets.

### T9 — PR #122 reconstructed with issue #128

The reconstructed product train should preserve read-only opportunity discovery and truthful qualification while adding:

```text
EmployerDutyWorkOrderSynthesizer
```

Authoritative work-order synthesis begins only after:

```text
WORK_ACCEPTED
OR verified assignment evidence
OR accountable operator records an authoritative employer instruction
```

Before that, only a non-authoritative preview is allowed.

### T10 — Canary B passed

Canary B proves:

- employer facts remain separate from AI inference;
- every duty and acceptance criterion is traceable;
- best practices do not silently override employer instructions;
- verified skills are used;
- work breakdown and KPI plans are deterministic and idempotent;
- contradictions fail closed;
- one verified employer amendment produces a revision diff and impact analysis;
- scope, price, deadline, contract and safety changes escalate;
- no external commitment occurs automatically.

### T11 — One read-only connector proven

Preferred first candidates:

```text
Gmail read-only search
Google Drive read-only retrieval
```

Require minimum OAuth scopes, consent, Secret Manager resolution, audit attribution, rate limits, emergency stop and token revocation. Sending, modifying, scheduling and committing externally remain unavailable.

## Decision lineage consolidated from the program discussion

### Evidence outranks assertion

An operator statement can authorize an attempt. It cannot create missing logs, receipts, artifacts, reviews or successful execution.

### Isolated staging precedes production

The first live target is a bounded staging pilot with strict budget, identity and data controls.

### CI and mainline convergence precede downstream trains

PR #123 is first. PR #121, PR #122 and PR #129 require reconstruction or rebinding after the mainline moves.

### Platform proof precedes product-autonomy proof

Cloud Run and Canary A come before issue #128 and Canary B. This separates infrastructure failure from autonomous-product behavior.

### Accepted work is the authoritative trigger

Discovery is not employment. A posting may generate analysis and previews, but accepted or verified assignment evidence is required before creating authoritative employer obligations.

### Internal autonomy is allowed; external commitment is not implied

AIGC may autonomously:

- plan internal work;
- create internal work orders;
- assign approved internal agents;
- measure progress and quality;
- reconcile low-risk internal clarifications.

Separate approval remains required for:

- employment and contract acceptance;
- scope, price and committed deadline changes;
- employer communication;
- application or deliverable submission;
- credential use;
- cloud resource creation;
- payment, purchasing or production deployment.

## Evaluator commands

From a clean checkout of this branch:

```bash
python -m src.core.current_repository_truth_procurement
pytest -q tests/test_current_repository_truth_procurement.py
```

Write a deterministic coordination receipt:

```bash
python -m src.core.current_repository_truth_procurement \
  --output reports/artifacts/governance/current-repository-truth-procurement.json
```

The receipt identifies:

- the first incomplete transition;
- accountable actor;
- required actions;
- required evidence;
- stop conditions;
- whether external mutation is required;
- whether safety invariants remain preserved.

## Completion-request evaluation

Code may evaluate whether a transition appears ready, but it does not mutate the ledger automatically.

A completion request is blocked when:

- a predecessor transition is incomplete;
- evidence references are insufficient;
- accountable attestation is missing;
- the transition is already complete;
- blocked recovery has no evidence.

This keeps state changes reviewable and prevents an AI from marking its own program complete.

## Current truth

```text
transition targets: 11
completed transitions: 0
safety invariants: 8
next transition: T1_HOSTED_VALIDATION_SUCCESSFUL
hosted CI recovered: false
issue #124 resolved: false
PR #123 admitted: false
PR #129 admitted: false
Cloud Run runtime implemented: false
staging cloud resources created: false
Canary A passed: false
Canary B passed: false
read-only connector proven: false
external action performed by this procurement: false
```

## Boundary

```text
operator_review_required=true
automatic_merge_allowed=false
self_approval_allowed=false
automatic_external_commitment_allowed=false
hosted_ci_replacement_allowed=false
external_action_performed=false
```

The proper measure of momentum is not the number of booleans changed. It is the number of claims converted into reproducible, attributable and reversible operational evidence.
