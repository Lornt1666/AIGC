# AIGC Identity Operational Evidence Gate v1

Status: `IMPLEMENTED_ON_REVIEW_BRANCH_PENDING_CI_AND_OPERATOR_REVIEW`  
Base revision: `5847320a2bd706bb241bbd78e9ee1f2feb258e3f`  
Branch: `codex/identity-operational-evidence-gate-v1`  
Google Identity Platform configured: **No**  
Secret accessed: **No**  
User onboarded: **No**  
Production identity activated: **No**  
External action performed: **No**

## Objective

Turn AIGC's existing production identity baseline and future Identity Platform staging receipt into one deterministic, fail-closed operational-evidence decision without configuring Google Cloud, resolving a secret, onboarding a user, or activating identity.

The gate does not create staging evidence. It evaluates evidence supplied later through a separately authorized process.

## Evidence model

```text
production identity baseline
        +
optional expected staging project reference
        +
optional identity_platform_staging_receipt
        ↓
strict contract validation
        ↓
revision / project / time binding
        ↓
identity operational evidence evaluation
        ↓
INTERNAL_ONLY
STAGING_EVIDENCE_REJECTED
STAGING_EVIDENCE_ACCEPTED_PENDING_OPERATOR_REVIEW
```

The final state never implies production completion or production activation.

## Canonical artifacts

```text
schemas/identity_operational_evidence_evaluation.schema.json
src/core/identity_operational_evidence.py
tests/test_identity_operational_evidence.py
```

Existing controlling artifacts remain:

```text
config/production_identity_platform_baseline.json
schemas/production_identity_platform_baseline.schema.json
schemas/identity_platform_staging_receipt.schema.json
docs/PRODUCTION_IDENTITY_PLATFORM_BASELINE_V1.md
```

## Current exact result

With the canonical baseline and no staging receipt, the expected state is:

```text
status: INTERNAL_ONLY
implemented_internal: true
staging_evidence_accepted: false
readiness_review_eligible: false
production_complete: false
production_activation_authorized: false
```

Unresolved configuration includes:

```text
IDENTITY_PLATFORM_BASELINE_PROJECT_UNBOUND
IDENTITY_PLATFORM_PROJECT_REFERENCE_MISSING
SESSION_PEPPER_PROJECT_UNRESOLVED
```

Missing operational observations include real Google sign-in, key rotation, revocation, session rotation, logout, restart persistence, cross-tenant and cross-project denial, provider-outage behavior, and redaction review.

Authority remains absent for provider configuration, secret access, staging-user onboarding, and production identity activation.

## Receipt acceptance rules

A staging receipt is accepted only when:

1. it satisfies the strict `identity_platform_staging_receipt` contract;
2. it is bound to an exact 40-character Git revision;
3. its revision equals the evaluated revision;
4. its project reference equals the expected staging project reference;
5. its result is `PASS`;
6. every required positive and negative check is true;
7. no raw tokens were persisted or logged;
8. public self-registration remained disabled;
9. no production user was used;
10. it is not future-dated;
11. operator review remains required.

Malformed, failed, wrong-revision, wrong-project, future-dated, production-user, or authority-expanding evidence fails closed.

## Three separate decisions

### 1. Staging evidence accepted

Means the supplied receipt is structurally valid and correctly bound to the expected project and revision.

It does **not** mean the canonical baseline is configured.

### 2. Readiness review eligible

Requires accepted staging evidence plus no unresolved canonical configuration and no missing operational evidence.

The current v1 baseline intentionally keeps the project ID null, session-pepper project unresolved, provider configuration unauthorized, secret access unauthorized, user onboarding unauthorized, and production activation unauthorized. Therefore the current branch cannot recommend readiness promotion.

A separately reviewed configuration/activation contract must exist before this state can become true.

### 3. Production identity activation

Remains an independent operator-controlled decision after operational evidence, privacy/security review, incident/rollback readiness, and deployment authority.

The gate schema fixes `production_complete=false` and never performs activation.

## Operational requirements inventory

The exact future staging process must prove:

- isolated staging Identity Platform project;
- Google sign-in for an operator-controlled test identity only;
- public self-registration disabled;
- reviewed redirect origins and domains;
- trusted provider-subject mapping;
- session pepper through approved workload identity and Secret Manager;
- valid signature, issuer, audience, expiry, and provider checks;
- wrong signature, issuer, audience, expiry, and replay denial;
- public-key rotation;
- provider revocation synchronization;
- session issue, rotation, logout/revocation, and restart persistence;
- cross-tenant and cross-project denial;
- provider outage fail-closed behavior;
- raw-token and claim redaction review;
- exact-revision staging receipt;
- accountable operator review.

## Current readiness impact

```text
canonical score: 74.50 / 100
score movement from this PR: 0.00
production_identity_access: partial
production_ready: false
blockers closed: 0
```

This PR improves evidence processing, not operational maturity.

## Security and privacy boundary

- no provider API call;
- no network access;
- no OAuth or Identity Platform configuration;
- no Secret Manager access;
- no credential, assertion, email, user profile, or raw token is accepted by the gate;
- receipt metadata contains only project/revision/test-subject references and booleans permitted by the existing staging contract;
- no production users;
- no public registration;
- no automatic readiness promotion;
- no production activation;
- no external action.

## Required CI gates

1. schema validation;
2. AEC-001 constitutional validation;
3. committed-content secret/redaction scan;
4. procurement smoke stages;
5. current-baseline blocker test;
6. valid synthetic receipt acceptance without readiness or activation claim;
7. revision and project mismatch denial;
8. invalid and future-dated receipt denial;
9. unbound revision and malformed project denial;
10. deterministic evaluation identity and input immutability;
11. complete repository test suite;
12. readiness evaluator remains `74.50`, production false, and five blockers;
13. exact-head operator review;
14. separate merge decision.

## Rollback

Before merge, close or abandon the review branch.

After merge, revert the schema, evaluator, tests, and runbook as one bounded unit. No provider, secret, user, data, session, cloud, or external-system rollback is required because the gate performs no live operation.

## Definition of done

- current identity blockers are emitted deterministically;
- the existing staging receipt is strictly validated at runtime;
- revision, project, and future-time mismatch fail closed;
- a valid synthetic receipt can be accepted without claiming readiness or activation;
- readiness-review eligibility remains false under the canonical unresolved baseline;
- production completion remains impossible through this evaluator;
- all tests and CI pass;
- no readiness score or blocker state changes;
- the accountable operator retains the merge decision.
