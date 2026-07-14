# AIGC Exact Identifier and Split Authorization Packet v1

Status: `IMPLEMENTED_INTERNAL_AWAITING_IDENTIFIERS`  
Decision basis: `main@f5a264de374fe18b1db0090acaa8935ac55bb975`  
Readiness at design time: `74.50 / 100`  
External action performed: **No**

## Objective

Create one exact, non-secret identifier submission packet and two independent authorization receipts:

1. isolated staging identity authorization;
2. production deployment authorization.

This architecture separates operator approval from operational effectiveness. A receipt can say `APPROVED` and still evaluate as ineffective when its identifiers, revision, lifetime, target bindings, release gate, readiness score, or blocking-gap truth do not satisfy the admitted contracts.

## Canonical artifacts

```text
schemas/exact_identifier_submission_packet.schema.json
schemas/staging_identity_authorization_receipt.schema.json
schemas/production_deployment_authorization_receipt.schema.json
schemas/exact_authorization_submission_evaluation.schema.json
config/exact_identifier_submission_packet.json
src/core/exact_authorization_submission.py
tests/test_exact_authorization_submission.py
docs/governance/evolution/AIGC_EXACT_IDENTIFIER_AND_SPLIT_AUTHORIZATION_V1.md
```

## Identifier packet

The canonical packet starts in:

```text
status: AWAITING_IDENTIFIERS
automatic_apply_allowed: false
external_action_performed: false
```

It accepts references only. It never accepts raw secret values.

### Isolated staging identity references

```text
gcp_project://<staging-project-id>
gcp_service_account://<project-id>/<service-account-email>
gcp_secret://<project-id>/aigc-session-pepper/<positive-numeric-version>
staging_subject://<opaque-operator-controlled-reference>
https://<explicit-origin>
https://<explicit-origin>/<explicit-callback>
```

Symbolic secret versions such as `latest`, wildcard origins, insecure HTTP origins, raw credentials, and production users are not admissible.

### Production deployment references

```text
gcp_project://<production-project-id>
gcp_service_account://<project-id>/<service-account-email>
REL-<release-id>
<64-hex release-candidate digest>
<64-hex readiness-truth digest>
sha256:<64-hex immutable artifact digest>
dns_name://<production-domain>
cloud_sql://<project>/<instance>/<database>
gcs_state://<project>/<bucket>/<state-object>
PRG-<24 uppercase hex release-gate receipt id>
```

`READY_FOR_OPERATOR_REVIEW` requires every staging and production reference plus an empty unresolved-identifier list. That status grants no authority by itself.

## Staging identity authorization receipt

The staging receipt is exact-revision, exact-packet, exact-target, single-use, and time-bounded.

Maximum lifetime enforced by the evaluator:

```text
4 hours
```

It may explicitly authorize any reviewed subset of:

```text
staging_configuration_review_authorized
identity_platform_configuration_authorized
workload_identity_creation_authorized
session_pepper_creation_authorized
session_pepper_access_authorized
test_subject_onboarding_authorized
staging_sign_in_authorized
```

It can never authorize:

```text
production_identity_activation_authorized
production_deployment_authorized
automatic_apply_allowed
```

A malformed, denied, future-dated, expired, overlong, revision-mismatched, packet-digest-mismatched, or target-mismatched receipt evaluates ineffective.

## Production deployment authorization receipt

The production receipt is separately exact-revision, exact-packet, exact-release, exact-target, single-use, and time-bounded.

Maximum lifetime enforced by the evaluator:

```text
1 hour
```

An `APPROVED` receipt must bind:

- exact release ID;
- exact release-candidate digest;
- exact readiness-truth digest;
- exact immutable artifact digest;
- exact production project;
- exact deployment workload identity;
- exact domain;
- exact database;
- exact remote state;
- exact release-gate receipt;
- release-gate result `PERMIT`.

It can authorize:

```text
production_identity_activation_authorized
production_deployment_authorized
```

but only becomes effective when the evaluator also verifies:

```text
source_revision == exact_revision
readiness_score >= max(90, configured threshold)
production_ready == true
blocking_gaps == []
production_release_gate_result == PERMIT
```

At the current readiness of `74.50`, a production receipt remains ineffective even when its operator decision is `APPROVED`.

## Evaluation states

The evaluator emits one contract-bound result containing:

- packet readiness;
- staging receipt presence and effectiveness;
- staging rejection reasons;
- production receipt presence and effectiveness;
- production rejection reasons;
- readiness score;
- production-ready truth;
- blocking gaps.

The evaluation always fixes:

```text
operator_review_required: true
automatic_apply_allowed: false
external_action_performed: false
```

The evaluator does not call a provider, access a secret, onboard a subject, create a resource, run Terraform, activate identity, or deploy.

## Submission sequence

### Phase 1 — Identifier submission

1. Copy `config/exact_identifier_submission_packet.json` into a review branch.
2. Replace only the null and empty identifier fields with exact non-secret references.
3. Set `status` to `READY_FOR_OPERATOR_REVIEW`.
4. Set `unresolved_identifiers` to `[]`.
5. Keep all safety fields unchanged.
6. Run strict schema validation and full CI.
7. Obtain exact-head operator disposition.
8. Merge only the review-ready identifier packet.

### Phase 2 — Staging identity receipt

1. Compute the canonical SHA-256 packet digest.
2. Bind the receipt to the exact repository revision and packet digest.
3. Bind every staging target exactly.
4. Select explicit staging scopes.
5. Use an issue and expiry window no longer than four hours.
6. Obtain accountable-operator approval.
7. Evaluate the receipt.
8. Perform no action unless the evaluator reports the staging authorization effective.
9. Record provider evidence through the existing staging receipt and operational-evidence gate.

### Phase 3 — Production deployment receipt

1. Do not issue while readiness is below 90, blockers exist, or the release gate is not `PERMIT`.
2. Bind exact release, artifact, project, identity, domain, database, remote state, and release-gate evidence.
3. Use an issue and expiry window no longer than one hour.
4. Obtain accountable-operator approval.
5. Evaluate against the exact canonical readiness report.
6. Perform no action unless the evaluator reports production authorization effective.
7. Continue to require manual execution and audit evidence; automatic apply remains prohibited.

## Failure and rollback

Before merge, close or abandon the branch.

After merge, revert the eight-file contract unit. No cloud, provider, secret, identity, database, DNS, Terraform, deployment, or external-system rollback is needed because this unit performs no live action.

Expired, mismatched, reused, stale, malformed, or denied receipts must be discarded and replaced by new exact-revision receipts. A receipt must never be edited in place after issuance.

## Current truth boundary

```text
identifier packet: AWAITING_IDENTIFIERS
staging authorization effective: false
production authorization effective: false
readiness: 74.50 / 100
production ready: false
automatic apply: false
external action performed: false
```
