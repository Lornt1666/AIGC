# AIGC Deployment Baseline Revalidation — Post-Connector Main v2

Status: `REVALIDATION_PENDING_CI_AND_OPERATOR_REVIEW`  
Pull request: `#99`  
Canonical base: `main@18bb523845b22a8d7b97a7a15618145fbb5047ff`  
Previous deployment head: `07e378497d5998dd9e97bcf55a4815a086198eae`  
Rollback branch: `codex/production-deployment-baseline-v1-pre-admitted-connector-sync`  
External action performed: **No**

## Objective

Revalidate the existing fail-closed, no-resource production deployment baseline after admission of the identity, readiness, and disabled connector foundations.

## Current repository relationship

PR #98 is merged. PR #99 now targets canonical `main` directly rather than the historical connector branch. The deployment branch copies of the Secret Manager resolver and tests were aligned byte-for-byte with the admitted connector hardening before retargeting:

- authorized access requires a positive numeric secret version;
- adapter-facing material is a read-only view backed by a zeroizable buffer;
- symbolic versions, unresolved projects, unauthorized access, and cross-project access fail before a client call.

The historical stacked-dependency receipt remains historical evidence only. Current review eligibility is established by this direct-main PR, its exact synthetic merge candidate, and fresh CI.

## Deployment truth boundary

The baseline remains no-resource and default-deny:

- no `google_*` resources are declared;
- Terraform apply authority is false;
- staging and production project IDs are unresolved;
- domain, DNS authority, workload identity, network, database instance, image digest, and release permit are unresolved;
- no credential, secret, connector, provider, or cloud action is performed;
- no deployment is performed;
- production readiness remains false.

## Expected readiness result

The canonical score is expected to remain `66.80 / 100` with all five blocking gaps preserved:

```text
security_privacy_wiring
transactional_persistence
production_identity_access
approved_external_connectors
production_deployment
```

PR #99 does not change the readiness ledger. `production_deployment` remains `planned` until reviewed resource modules and exact-revision staging observations establish migration, health, monitoring, canary, rollback, restore, and recovery evidence.

## Required gates

1. contract validation;
2. AEC-001 constitutional validation;
3. committed-content secret/redaction scan;
4. procurement smoke stages;
5. complete repository test suite;
6. dependency-currentness classification appropriate for a direct-main evaluation;
7. readiness evaluation reproducing `66.80`;
8. test and readiness artifact uploads;
9. exact-head operator review;
10. separate merge decision.

## Rollback

Before merge, close PR #99 or restore the deployment branch to the preserved rollback head. After merge, revert the deployment baseline as one reviewed unit. No cloud, provider, credential, secret, data, or external-system rollback is required because no live resource authority is activated.
