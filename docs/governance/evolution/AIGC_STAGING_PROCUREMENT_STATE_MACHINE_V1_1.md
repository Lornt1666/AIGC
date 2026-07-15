# AIGC Staging Procurement State Machine v1.1

Status: `IMPLEMENTED_INTERNAL_NO_PROVIDER_ACTION`  
Decision basis: `main@208dd3dd26beead2c90aa4ab141f8fa935f668b4`  
Expected readiness movement: `0.00`  
External action performed by this unit: **No**

## Purpose

Repair the staging procurement deadlock admitted in v1 and establish an executable governance sequence that can move from target specification to provider discovery, isolated state bootstrap, identity bootstrap, and a verified provider submission without confusing authorization with evidence.

The unit remains repository-only. It does not issue a receipt, call Google Cloud, access Secret Manager, run Terraform, configure Identity Platform, mutate DNS, onboard a subject, sign in, deploy, or perform any external action.

## Canonical artifacts

```text
config/staging_identity_procurement_readiness_pack.json
schemas/staging_identity_procurement_readiness_pack.schema.json
schemas/provider_discovery_authorization_receipt.schema.json
schemas/provider_discovery_evidence_receipt.schema.json
schemas/staging_plan_authorization_receipt.schema.json
schemas/staging_plan_evidence_receipt.schema.json
schemas/staging_apply_authorization_receipt.schema.json
schemas/staging_post_apply_operational_evidence.schema.json
schemas/staging_procurement_state_evaluation.schema.json
src/core/staging_identity_procurement_readiness.py
src/core/staging_procurement_contracts.py
src/core/staging_procurement_evaluator.py
tests/test_staging_identity_procurement_readiness.py
tests/staging_procurement_test_helpers.py
docs/governance/evolution/AIGC_STAGING_PROCUREMENT_STATE_MACHINE_V1_1.md
```

## Corrected truth model

The v1 template schema permanently fixed the artifact to `TEMPLATE` while the evaluator required `SUBMISSION`. Version 1.1 permits both forms:

```text
TEMPLATE
SUBMISSION
```

The committed canonical artifact remains:

```text
artifact_kind: TEMPLATE
status: TARGET_SPECIFICATION
pack_id: null
```

It has no authority and cannot be consumed.

A future submission receives:

```text
pack_id
created_at
expires_at
transition evidence
per-phase consumption state
```

The maximum submission lifetime is seven days. Revoked, expired, future-dated, superseded, or invalidly transitioned submissions fail closed.

## State machine

Only these forward transitions are admissible:

```text
TARGET_SPECIFICATION
  -> DISCOVERY_READY_FOR_REVIEW
  -> DISCOVERY_EVIDENCE_ACCEPTED
  -> STATE_BACKEND_PLAN_READY
  -> STATE_BACKEND_BOOTSTRAPPED
  -> IDENTITY_BOOTSTRAP_PLAN_READY
  -> READY_FOR_OPERATOR_REVIEW
```

Any active state may transition to `SUPERSEDED`. Each non-initial transition requires a reason and evidence digest.

### 1. Target specification

Records intended non-secret targets without claiming existence:

```text
staging project ID and reference
WIF pool/provider IDs
plan/apply/runtime service-account IDs
required APIs
state bucket reference
staging domain reference
GitHub repository, owner, ref, and workflow bindings
```

Required APIs include:

```text
cloudresourcemanager.googleapis.com
iam.googleapis.com
iamcredentials.googleapis.com
identitytoolkit.googleapis.com
secretmanager.googleapis.com
serviceusage.googleapis.com
storage.googleapis.com
sts.googleapis.com
```

### 2. Provider discovery authorization

The discovery receipt is read-only, exact-revision, exact-pack, exact-project, single-use, and valid for no more than four hours.

It may authorize only:

```text
READ_PROJECT_METADATA
READ_ENABLED_APIS
READ_EXISTING_IAM
READ_SERVICE_ACCOUNT_KEY_COUNTS
READ_STATE_BACKEND_METADATA
READ_IDENTITY_PLATFORM_CONFIGURATION
```

It permanently denies mutation and secret-value access.

### 3. Provider discovery evidence

Discovery evidence is separate from authorization. A real evidence receipt records that provider reads occurred and therefore fixes:

```text
provider_read_performed: true
external_action_performed: true
mutation_performed: false
secret_value_access_performed: false
```

It records existing, missing, bootstrap-required, and manual-configuration resources without storing a raw secret value.

### 4. State-backend plan

A state-backend plan may be authorized only after accepted discovery evidence. It plans the state foundation and controls only.

The GCS state target is specified before creation, but verified state references, locking, rollback generation, and control attestations are not required until post-apply evidence exists.

### 5. State-backend evidence

Post-apply operational evidence binds:

```text
apply authorization
accepted plan evidence
plan artifact digest
verified resources
key counts
numeric secret references when applicable
rollback result
```

The provider-action and Terraform-apply truth belongs in this evidence contract, never in an authorization receipt.

### 6. Identity bootstrap plan

Identity bootstrap planning requires the state backend to be `BOOTSTRAPPED_VERIFIED`.

It may plan:

```text
required API enablement
WIF pool and GitHub OIDC provider
separate plan/apply/runtime service accounts
secret containers and versions
Identity Platform Google provider configuration
staging origins and redirects
operator-controlled test subject
```

Numeric secret versions are not prerequisites for the plan. They become mandatory only in the final verified submission after the versions exist.

### 7. Verified provider submission

`READY_FOR_OPERATOR_REVIEW` requires:

```text
all required APIs verified enabled
billing, Identity Platform, and production-data absence verified
WIF resources bound to the selected project number
three distinct service accounts in the selected project
key_status: VERIFIED
verified_user_managed_key_count: 0
one canonical OAuth-client-secret numeric reference
a separate session-pepper numeric reference
matching domain, origin, and redirect host
verified state backend and rollback generation
operator-controlled non-production subject
separate bootstrap administrator
least privilege with Owner and Editor denied
accepted discovery, state, and identity evidence bindings
unresolved_requirements: []
```

The status grants no plan, apply, identity, sign-in, or production authority.

## Plan and apply separation

Plan authorization remains read-only and fixes:

```text
mutation_authorized: false
terraform_apply_authorized: false
```

Plan evidence must be accepted and binds the exact plan artifact, resource list, IAM delta, origins, redirects, and numeric secret references present at planning time.

Apply authorization is separately operator-approved, maximum one hour, and binds:

```text
exact revision
pack digest
phase and project
discovery evidence ID and digest
plan authorization ID
plan evidence ID and digest
plan artifact digest
exact resources
exact IAM delta
exact origins and redirects
exact secret references
rollback instructions digest
```

An approved apply receipt explicitly authorizes the reviewed staging mutation and Terraform apply, but records no execution:

```text
provider_action_performed: false
terraform_apply_performed: false
external_action_performed: false
```

Production identity activation and production deployment remain permanently denied.

## Secret and key truth

The OAuth client secret has one canonical location:

```text
verified_provider_state.identity_provider.oauth_client_secret_reference
```

The session pepper remains separate:

```text
verified_provider_state.session_security.session_pepper_secret_reference
```

Both require immutable positive numeric versions in a final verified submission.

Templates do not claim zero user-managed keys:

```text
key_status: UNVERIFIED
verified_user_managed_key_count: null
```

Final readiness requires:

```text
key_status: VERIFIED
verified_user_managed_key_count: 0
```

## Consumption and replay protection

The pack tracks independent single-use phases:

```text
provider_discovery
state_backend_plan
state_backend_apply
identity_bootstrap_plan
identity_bootstrap_apply
final_review
```

A consumed phase cannot be authorized again under the same pack. A new pack must supersede the previous one.

## Validation

Every supplied pack, authorization receipt, evidence receipt, and evaluation output is validated through Draft 2020-12 JSON Schema with format checking before trust decisions are made.

Unknown fields, malformed identifiers, nonnumeric secret versions, insecure URLs, mismatched targets, stale receipts, overlong TTLs, invalid transitions, reused phases, and plan/apply drift fail closed.

## Rollback

Before merge, close the branch.

After merge, revert the v1.1 contract unit. No provider or external-system rollback is needed because this unit performs no live action.

PR #109 remains historical source material only. After this current-main convergence is admitted, PR #109 should be closed as superseded without merge.
