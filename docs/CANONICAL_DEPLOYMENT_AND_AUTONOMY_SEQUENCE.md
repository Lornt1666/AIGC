# AIGC Canonical Deployment and Autonomy Sequence

## Status

```text
CONTRACT_BACKED_COORDINATION_ARTIFACT
HOSTED_CI_RECOVERED=false
PR_123_ADMITTED=false
CLOUD_RUN_RUNTIME_IMPLEMENTED=false
CANARY_A_PASSED=false
CANARY_B_PASSED=false
EXTERNAL_ACTION_PERFORMED=false
```

This runbook is the human-readable companion to:

```text
config/canonical_deployment_and_autonomy_sequence.json
schemas/canonical_deployment_and_autonomy_sequence.schema.json
src/core/canonical_deployment_sequence.py
```

It consolidates the currently procured deployment, staging, work-acquisition and autonomous work-execution decisions into one fail-closed sequence.

The document and manifest grant no merge, billing, credential, cloud-resource, Terraform-apply, job-submission, messaging, scheduling, contract, delivery or production authority.

## Validation

From the repository root:

```bash
python -m src.core.canonical_deployment_sequence
pytest -q tests/test_canonical_deployment_sequence.py
```

The command validates the contract and semantic invariants, then prints a deterministic coordination receipt containing the current stage and next admissible action.

## Exact observed bindings

At the time this sequence was instantiated:

```text
main: 84d8fbe57e65eb9b93070646934b71863ac5a4db
PR #123: 8f6285db20d08ab1ebfabb5dd757bb9e186cf5e0
PR #121: bccce481fb1efae8deb52fbc41eec209620031fa
PR #122: f2e69ed5e4622aa1e83fddebaa18e449da23bd54
CI incident: issue #124
operator remediation task: issue #127
employer-duty automation: issue #128
```

Any change to a bound head or to `main` requires the sequence to be reviewed and rebound before it is used as current evidence.

## Canonical critical path

```text
S1  Restore trustworthy hosted CI
→ S2  Admit PR #123 and converge main
→ S3  Reconstruct staging plan/apply authorization gates
→ S4  Implement bounded Cloud Run staging runtime
→ S5  Activate isolated Google Cloud staging
→ S6  Complete Canary A platform proof
→ S7  Reconstruct PR #122 on the proven mainline
→ S8  Complete Canary B employer-duty autonomy proof
→ S9  Enable one separately approved read-only connector
```

No later stage may be represented as complete while an earlier dependency is incomplete.

## Stage 1 — restore hosted CI

The immediate blocker is the GitHub Actions pre-checkout failure tracked by issue #124.

Required evidence:

- genuine non-sensitive GitHub UI banner and restriction category;
- valid GAR remediation receipt;
- unchanged exact-head PR #123 hosted run;
- checkout and real workflow steps;
- successful tests;
- provider-discovery evidence artifact;
- Terraform evidence artifact;
- test artifact;
- readiness artifact;
- valid GHR recovery verification;
- accountable operator evidence review.

A rerun request, operator assertion or zero-step result does not complete this stage.

## Stage 2 — admit PR #123

After hosted recovery:

1. perform exact-head technical review;
2. record a separate accountable-operator disposition;
3. merge only with expected-head protection;
4. record the resulting exact `main`;
5. run hosted mainline CI and verify evidence.

Automatic merge remains prohibited.

## Stage 3 — reconstruct PR #121

PR #121 must be reconstructed on the resulting hardened mainline rather than treated as automatically current.

Preserve:

- `SIP-*` exact-revision staging plan authorization;
- exact project and Terraform fingerprint binding;
- short authorization lifetime;
- `SIA-*` single-use exact-plan apply authorization;
- saved-plan SHA-256 binding;
- separate plan and apply authority;
- no production authority;
- no automatic apply.

## Stage 4 — bounded Cloud Run staging runtime

The current baseline names Cloud Run v2, but the repository still needs a resource-bearing staging runtime implementation.

The bounded runtime train should include:

```text
Dockerfile
.dockerignore
non-root runtime user
/health endpoint
Artifact Registry repository
Cloud Run v2 service
runtime service account
Secret Manager references
private Cloud SQL connectivity
VPC access
minimum required IAM
structured logging
staging-only gates
zero production authority
```

The build path must produce:

```text
immutable image digest
SBOM
build provenance
image signature
vulnerability scan
deployment manifest
```

Defining these resources does not authorize their creation.

## Stage 5 — isolated staging activation

Use issue #116 as the operational checklist.

Required order:

```text
dedicated staging project
→ approved billing and CAD 50 budget
→ northamerica-northeast2
→ remote Terraform state
→ WIF and least-privilege IAM
→ accepted read-only provider discovery
→ SIP plan authorization
→ provider-backed saved plan
→ accountable plan review
→ SIA apply authorization
→ exact-plan apply
```

Use no production project and no real customer data.

## Canary A — platform proof

Canary A must pass before PR #122 or issue #128 is introduced into staging.

Required journey:

```text
operator authenticates
→ /health passes
→ application connects to PostgreSQL
→ operator creates a basic internal work order
→ governance artifacts are generated
→ data persists
→ audit record is written
→ logs, metrics and alerts are observed
→ rollback is demonstrated
```

Operational evidence must include:

- allowlisted operator authentication;
- secure session controls;
- successful migrations;
- read/write and transaction rollback tests;
- concurrent-conflict behaviour;
- connection pooling;
- backup and isolated restore;
- observed RPO/RTO;
- health, readiness and synthetic journey evidence;
- alert and budget-notification delivery;
- prior-image rollback.

Canary A proves the platform can run, persist, observe and recover safely. It does not require employer-duty synthesis.

## Stage 7 — reconstruct PR #122

Only after Canary A is accepted:

- reconstruct the Jobs & Interviews and cockpit work on the proven mainline;
- preserve read-only opportunity discovery;
- preserve truthful qualification requirements;
- preserve blocked application, messaging, scheduling, offer acceptance and credential use;
- implement issue #128 as mandatory scope;
- run complete CI;
- complete exact-head review and separate disposition.

Do not extend the stale stacked PR #122 head as though it were current.

## Canary B — autonomous accepted-work proof

Issue #128 is Canary B.

Authoritative trigger:

```text
Quest lifecycle = WORK_ACCEPTED
OR verified assignment evidence exists
OR accountable operator records an authoritative employer instruction
```

Before this trigger, AIGC may generate only a non-authoritative preview.

Required journey:

```text
verified employer source
→ qualified candidate
→ accepted Quest
→ employer-duty normalization
→ requirements traceability
→ best-practice mapping
→ capability-gap analysis
→ autonomous work breakdown and KPI plan
→ governed internal execution
→ employer-instruction reconciliation
```

The synthesizer must preserve employer facts separately from AI inference and recommendations.

Required release gates:

- traceability;
- determinism;
- idempotency;
- contradiction control;
- verified capability truth;
- legal and safety precedence;
- analytical integrity;
- revision governance;
- external-action isolation.

Introduce one verified employer amendment and prove:

```text
instruction received
→ provenance verified
→ change classified
→ revision diff generated
→ scope and schedule impact calculated
→ low-risk internal clarification applied where policy permits
OR
→ consequential change escalated for accountable review
```

## Authority matrix

| Action | Automatic | Separate approval |
|---|---:|---:|
| Read approved employer evidence | Yes | No |
| Extract duties and requirements | Yes | No |
| Generate an internal work order after the accepted-work trigger | Yes | No |
| Assign approved internal agents | Yes | No |
| Measure progress and quality | Yes | No |
| Apply a low-risk internal clarification | Conditional | Policy-dependent |
| Change committed scope | No | Yes |
| Change price or deadline commitments | No | Yes |
| Send employer or client communication | No | Yes |
| Submit an application or deliverable | No | Yes |
| Accept employment or a contract | No | Yes |
| Use credentials or create cloud resources | No | Yes |

Canonical truth:

```text
autonomous_internal_planning=true
autonomous_internal_work_order_creation=true
autonomous_progress_analysis=true
autonomous_internal_reconciliation=true
automatic_external_commitment_allowed=false
self_approval_allowed=false
automatic_merge_allowed=false
external_action_performed=false
```

## Stage 9 — first connector

After Canary B, enable only one low-risk read-only connector, preferably:

```text
Gmail read-only search
OR
Google Drive read-only retrieval
```

Prove:

- explicit consent;
- minimal OAuth scope;
- Secret Manager reference resolution;
- audit attribution;
- rate limiting;
- emergency stop;
- token revocation;
- no send, form submission, scheduling, mutation or external commitment capability.

## Stop conditions

Stop and rebind or escalate if:

- a bound PR head or `main` changes;
- hosted CI again reports zero steps or missing artifacts;
- a dependency is skipped;
- Canary B is proposed before Canary A passes;
- a source statement cannot be distinguished from AI inference;
- verified capability evidence is absent;
- employer instructions contradict one another;
- scope, price, deadline, contract or safety changes lack review;
- a manifest or component claims self-approval, automatic merge or automatic external commitment;
- credentials, secret values or sensitive billing information appear in repository evidence.

## Current next admissible action

```text
Correct the actual GitHub Actions account or runner-allocation restriction,
create a valid GAR receipt from genuine non-sensitive observations,
and rerun unchanged PR #123 until checkout, real steps and all mandatory
artifact families execute successfully.
```

No Cloud Run implementation, staging apply, PR #122 reconstruction, Canary B execution, connector activation or external action is currently authorized by this coordination artifact.
