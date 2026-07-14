# AIGC Staging Identity Procurement Readiness Pack v1

Status: `IMPLEMENTED_INTERNAL_AWAITING_PROVIDER_REFERENCES`  
Architecture basis: `main@a5a0775c93223177dbab0b17a0c48fc0cda727f6`  
Readiness movement: `0.00`  
Provider action performed: **No**

## Objective

Define the complete repository-side procurement boundary needed before an authorized operator may generate a plan for an isolated Google Cloud Identity Platform staging environment.

This unit does not create a Google Cloud project, enable an API, create a workload-identity pool or provider, create a service account, access or create a secret, configure OAuth, create a state bucket, run Terraform, configure DNS, onboard a subject, perform sign-in, or deploy.

## Canonical artifacts

```text
config/staging_identity_procurement_readiness_pack.json
schemas/staging_identity_procurement_readiness_pack.schema.json
schemas/staging_identity_plan_authorization_receipt.schema.json
schemas/staging_identity_plan_evidence_receipt.schema.json
schemas/staging_identity_apply_authorization_receipt.schema.json
schemas/staging_identity_procurement_evaluation.schema.json
src/core/staging_identity_procurement.py
tests/test_staging_identity_procurement.py
docs/governance/evolution/AIGC_STAGING_IDENTITY_PROCUREMENT_READINESS_PACK_V1.md
```

## Canonical template

The committed configuration is a non-live template:

```text
artifact_kind: TEMPLATE
pack_id: null
status: AWAITING_PROVIDER_REFERENCES
requested_plan_phase: null
provider_action_performed: false
terraform_plan_performed: false
terraform_apply_performed: false
automatic_apply_allowed: false
external_action_performed: false
```

Known public GitHub bindings are fixed:

```text
repository: Lornt1666/AIGC
repository_id: 1287333065
repository_owner_id: 236225491
ref: refs/heads/main
workflow: .github/workflows/aigc-ci.yml@refs/heads/main
```

Every provider-controlled identifier remains null or unverified until direct evidence is supplied by an authorized Google Cloud operator.

## Procurement requirements

### Isolated staging project

A review-ready submission identifies one exact staging project ID, project reference, and numeric project number. It records verified billing, Identity Platform enablement, required API enablement, and absence of production data.

Required API services:

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

### Workload Identity Federation

The submission identifies:

```text
workload identity pool resource
GitHub OIDC provider resource
numeric repository and owner IDs
exact repository, ref, and workflow
attribute mapping fingerprint
attribute condition fingerprint
plan service account
apply service account
application runtime service account
```

The plan, apply, and runtime service accounts must be distinct. User-managed service-account keys must be zero. Long-lived keys and key export remain prohibited.

### Identity Platform Google provider

The submission records only non-secret references:

```text
Google OAuth Web Client ID
gcp_secret://<project>/aigc-google-oauth-client-secret/<numeric-version>
gcp_oauth_consent://<project>/<internal-or-external>
dns_name://<staging-domain>
https://<staging-origin>
https://<staging-origin>/<callback>
```

The OAuth client secret value must never enter GitHub, a receipt, a log, or an operator-visible artifact.

### Session security

The session pepper uses a separate immutable numeric Secret Manager version:

```text
gcp_secret://<project>/aigc-session-pepper/<numeric-version>
```

It must be distinct from the OAuth client secret reference. Raw values remain prohibited.

### Terraform state

The pack supports two independently reviewed phases.

#### `STATE_BACKEND_BOOTSTRAP`

The target bucket and state object are named, but the bucket is attested absent before bootstrap planning. No backend security control is claimed as already operational.

#### `STAGING_IDENTITY_CONFIGURATION`

The state backend must already be verified with:

```text
bucket preexists backend initialization
uniform bucket-level access
public access prevention
object versioning
retention policy
state locking
rollback generation reference
```

The state bucket bootstrap and identity configuration must never be authorized as one unreviewed operation.

## Plan authorization

The plan receipt is exact-revision, exact-pack-digest, exact-project, phase-specific, single-use, and valid for at most four hours.

It may authorize only:

```text
read project metadata
validate required APIs
validate existing resources
generate a Terraform/provider plan
calculate target and plan digests
```

It permanently denies:

```text
API enablement
resource creation, update, or deletion
IAM mutation
secret access or mutation
Terraform apply
DNS mutation
identity-provider configuration
test-subject onboarding
staging sign-in
```

The authorization receipt itself always records that no provider action, plan execution, apply, or external action has yet occurred.

## Plan evidence

A plan evidence receipt is created only after an effective plan authorization is used. It binds:

```text
exact revision
procurement-pack digest
plan authorization receipt
phase and project
plan artifact digest
target inventory digest
IAM delta digest
exact planned resource list
exact IAM delta
origins and redirects
numeric secret references
generation and review timestamps
```

A plan may be accepted only after operator review. Plan evidence may truthfully record provider reads and Terraform plan execution as external actions, but provider mutation and Terraform apply remain false.

## Apply authorization

An apply receipt is separate from plan authorization and may be issued only after accepted plan evidence exists. It binds the exact plan evidence ID and digest, plan artifact digest, resources, IAM delta, origins, redirects, secret references, project, revision, and rollback instructions.

Maximum lifetime:

```text
1 hour
single use
```

For state-backend bootstrap, only that exact bootstrap may be authorized. For staging identity configuration, state bootstrap is denied and the receipt must identify at least one explicit staging action. Production identity activation and production deployment are permanently denied.

The apply authorization receipt itself always records:

```text
provider_action_performed: false
terraform_apply_performed: false
external_action_performed: false
```

Actual action evidence belongs in a later post-action receipt.

## Fail-closed evaluator

The evaluator verifies:

- strict Draft 2020-12 contracts;
- pack submission and lifecycle validity;
- exact revision and canonical pack digest;
- required APIs;
- project consistency across WIF, service accounts, secrets, and state;
- distinct plan, apply, and runtime identities;
- domain, origin, and redirect consistency;
- state-backend phase readiness;
- plan receipt scope and lifetime;
- plan evidence acceptance;
- apply receipt exact-plan binding and lifetime.

The evaluator never issues a receipt or performs an action. Its output fixes:

```text
authorization_receipt_issued_by_evaluator: false
provider_action_performed: false
terraform_plan_performed: false
terraform_apply_performed: false
operator_review_required: true
automatic_apply_allowed: false
external_action_performed: false
```

## Acceptance criteria

1. The canonical template validates and remains inert.
2. Synthetic state-bootstrap and staging-identity submissions validate.
3. Missing required APIs fail schema validation.
4. Cross-project references and reused IAM identities fail closed.
5. Plan authorization remains read-only and exact-bound.
6. Expired or digest-mismatched authorization fails.
7. Plan evidence requires an effective authorization and operator acceptance.
8. Apply authorization requires accepted exact plan evidence.
9. Production scope injection fails schema validation.
10. Evaluations do not mutate their inputs.
11. Full CI preserves readiness at `74.50`, production false, and all five blockers.

## Next separately authorized step

After this architecture is admitted, an authorized operator may collect real non-secret provider references and submit a new pack with:

```text
artifact_kind: SUBMISSION
status: READY_FOR_PLAN_REVIEW
requested_plan_phase: STATE_BACKEND_BOOTSTRAP
unresolved_requirements: []
```

That submission still issues no permit and performs no provider action. A separate exact-head, time-bounded plan authorization remains mandatory.

## Rollback

Before merge, close or abandon the branch. After merge, revert this nine-file repository-only unit. No cloud, secret, identity, state, DNS, Terraform, deployment, or external-system rollback is required because this unit performs no live action.
