# AIGC Isolated Staging Identity Configuration Decision v1

Status: `DEFERRED_IDENTIFIERS`  
Decision basis: `main@a80a9458a50726ce175f6987155d84d44f6630e9`  
Environment: `isolated_staging`  
Google Cloud configured: **No**  
Secret created or accessed: **No**  
Test subject onboarded: **No**  
Staging sign-in enabled: **No**  
Production identity activated: **No**  
External action performed: **No**

## Objective

Define the exact configuration and authorization boundary that must exist before an isolated Google Cloud Identity Platform staging change may even be presented for operator review.

This artifact is not a provider configuration, Terraform module, OAuth grant, service-account creation request, Secret Manager mutation, user-onboarding instruction, or activation permit. It is a repository contract that records unresolved identifiers and fixes all live authorities to false.

## Canonical artifacts

```text
schemas/identity_staging_configuration_decision.schema.json
config/identity_staging_configuration_decision.json
tests/contracts/test_identity_staging_configuration_decision.py
docs/governance/evolution/AIGC_IDENTITY_STAGING_CONFIGURATION_DECISION_V1.md
```

## Required staging boundaries

### Identity Platform project

The decision requires one exact staging project reference:

```text
gcp_project://<project-id>
```

The current value is `null`. Production and staging projects must never be inferred from repository owner, billing account, local environment variables, or a provider default.

### Workload identity

The future review packet must identify one exact service account through:

```text
gcp_service_account://<project-id>/<service-account-email>
```

Required controls:

- GitHub OIDC federation only;
- repository allowlist includes only reviewed repositories;
- no long-lived service-account key;
- no key export;
- least privilege required;
- no workload-identity creation authority in this v1 contract.

### Session pepper

The future review packet must identify one exact immutable Secret Manager version:

```text
gcp_secret://<project-id>/aigc-session-pepper/<positive-numeric-version>
```

The contract rejects symbolic versions such as `latest`, raw secret values in the repository, raw values in receipts, and unreviewed secret rotation.

### Test-subject boundary

The future review packet must identify one operator-controlled staging subject:

```text
staging_subject://<opaque-reference>
```

The boundary requires:

- maximum one subject;
- no production user;
- no public registration;
- no profile-data persistence;
- no email address in evidence receipts;
- no public tenant discovery.

### Origin and redirect boundary

A review-ready packet requires explicit HTTPS origins and redirect URIs. Wildcards, HTTP origins, provider defaults, and inferred callback paths are prohibited.

## Decision states

### `DEFERRED_IDENTIFIERS`

The canonical repository state.

At least one required identifier remains unresolved. No review or provider action is eligible.

### `READY_FOR_OPERATOR_REVIEW`

All of the following must be present:

- exact staging project reference;
- exact workload-identity service account reference;
- exact numeric session-pepper secret version;
- exact operator-controlled test-subject reference;
- explicit HTTPS origins and redirect URIs;
- empty unresolved-identifier list.

This state still grants no live authority. It means only that a separately reviewed authorization packet could be considered.

## Authority boundary

This contract permanently allows only:

```text
contract_implementation_authorized = true
offline_validation_authorized = true
```

It permanently denies:

```text
staging_configuration_review_authorized
identity_platform_configuration_authorized
workload_identity_creation_authorized
session_pepper_creation_authorized
session_pepper_access_authorized
test_subject_onboarding_authorized
staging_sign_in_authorized
production_identity_activation_authorized
production_deployment_authorized
```

A future live action requires a separate, exact-revision, time-bounded authorization receipt. Editing this decision file cannot authorize a provider mutation.

## Relationship to the operational-evidence gate

The staging configuration decision defines what must be identified before staging work can be reviewed.

The identity operational-evidence gate evaluates what was later observed:

```text
configuration decision
→ separate operator authorization
→ isolated staging action
→ identity_platform_staging_receipt
→ identity operational-evidence evaluation
→ operator disposition
```

No stage automatically promotes readiness or production activation.

## Current unresolved identifiers

```text
staging_project_reference
workload_identity_service_account_reference
session_pepper_secret_reference
operator_controlled_test_subject_reference
authorized_origins_and_redirect_uris
```

## Acceptance criteria

The contract is accepted when:

1. the canonical deferred decision validates;
2. a fully resolved synthetic packet validates as review-ready;
3. review-ready status fails when any identifier is missing;
4. every live authority remains false;
5. symbolic secret versions fail;
6. long-lived or exported service-account keys fail;
7. production-user, public-registration, profile-persistence, wildcard-origin, and insecure-origin variants fail;
8. unknown fields fail;
9. CI preserves readiness at 74.50 and all five blockers;
10. operator review and merge remain separate.

## Rollback

Before merge, close or abandon the branch.

After merge, revert the schema, canonical decision, tests, and runbook as one unit. No Google Cloud, Identity Platform, OAuth, Secret Manager, workload identity, user, session, database, deployment, or external-system rollback is required because no live action is authorized or performed.

## Next separately authorized step

After the operator supplies exact staging identifiers, prepare a new review-only revision changing `decision_status` to `READY_FOR_OPERATOR_REVIEW` while keeping every live authority false.

Only after that revision is reviewed may a separate, time-bounded staging-configuration authorization contract be proposed. This v1 artifact must never be used as an apply permit.
