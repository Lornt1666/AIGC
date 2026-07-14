# AIGC Staging Identity Procurement Readiness Pack v1

Status: `IMPLEMENTED_INTERNAL_AWAITING_PROVIDER_REFERENCES`  
Decision basis: `main@a5a0775c93223177dbab0b17a0c48fc0cda727f6`  
External action performed: **No**

## Purpose

Define every non-secret reference and attestation needed before an isolated Google Cloud staging identity exercise can be planned. This unit creates contracts only. It does not create a project, enable an API, configure Identity Platform, access Secret Manager, create workload identity, run Terraform, modify DNS, onboard a subject, or perform sign-in.

## Procurement planes

1. Repository procurement: schemas, template, evaluator, tests, and review evidence.
2. Provider procurement: real project, API, WIF, OAuth, Secret Manager, state, domain, and subject references supplied later by an authorized cloud operator.

## Bound public GitHub identity

The template binds public repository metadata already verified through GitHub:

```text
repository_id: 1287333065
repository_owner_id: 236225491
repository: Lornt1666/AIGC
ref: refs/heads/main
workflow: Lornt1666/AIGC/.github/workflows/aigc-ci.yml@refs/heads/main
```

All Google Cloud and application identifiers remain unresolved.

## Required provider outputs

The future submission must include:

- isolated staging project ID and numeric project number;
- billing and Identity Platform attestations;
- exact enabled API service names;
- WIF pool and provider resource names;
- separate plan, apply, and runtime service-account references;
- attribute mapping and condition fingerprints;
- Google OAuth web client ID and numeric-version Secret Manager reference;
- OAuth consent configuration reference;
- session-pepper numeric-version Secret Manager reference;
- exact HTTPS domain, origin, and redirect URI;
- pre-existing GCS state reference and safety attestations;
- one opaque operator-controlled staging subject reference.

Raw secrets, private keys, test-user email, wildcard origins, symbolic secret versions, and user-managed service-account keys are prohibited.

## Plan and apply separation

The plan receipt is read-only, single-use, exact-revision and pack-digest bound, and limited to four hours. It can read metadata, validate resources, generate a Terraform plan, and calculate digests. It cannot authorize mutation or apply.

The apply receipt is separately issued only after plan review. It binds the exact plan digest, resource manifest, IAM delta, origin/redirect set, secret references, rollback instructions, project, revision, and pack digest. Its maximum lifetime is one hour.

Both receipts are authorization records, not execution evidence. Therefore they always retain:

```text
provider_action_performed: false
terraform_apply_performed: false
external_action_performed: false
automatic_apply_allowed: false
```

Only a later post-action evidence receipt may truthfully set external action to true.

## State bootstrap

The GCS backend must already exist before Terraform initialization. Acceptance evidence must confirm uniform bucket-level access, public-access prevention, object versioning, retention documentation, state locking, least privilege, and a rollback version reference.

## Current truth

```text
procurement pack: TEMPLATE
status: AWAITING_PROVIDER_REFERENCES
authorization receipt issued: false
provider action performed: false
terraform apply performed: false
external action performed: false
readiness movement: 0.00
```
