# AIGC Exact Identifier Packet Governance v1.1

Status: `IMPLEMENTED_INTERNAL_TEMPLATE_ONLY`  
Decision basis: `main@3afc8c2e5b75291b0459b0569e96afa3da6ac71c`  
Readiness movement: `0.00`  
Provider action performed: **No**  
Authorization receipt issued: **No**

## Purpose

Correct the v1 packet model before any real staging identifiers are submitted.

The v1 packet coupled staging and production readiness through one status and one unresolved-identifier list. It also embedded an authorization basis revision inside the packet while the evaluator separately required the same revision, creating avoidable self-reference.

v1.1 makes the committed JSON a non-live template, separates staging and production readiness, and moves exact revision stamping into the evaluator.

## Canonical artifacts

```text
config/exact_identifier_submission_packet.json
schemas/exact_identifier_submission_packet.schema.json
schemas/exact_authorization_submission_evaluation.schema.json
src/core/exact_authorization_submission.py
tests/test_exact_authorization_submission.py
docs/governance/evolution/AIGC_EXACT_IDENTIFIER_PACKET_GOVERNANCE_V1_1.md
```

The staging and production authorization receipt schemas remain unchanged by this narrow correction.

## Template boundary

The committed configuration is always:

```text
artifact_kind: TEMPLATE
packet_id: null
staging_status: AWAITING_IDENTIFIERS
production_status: AWAITING_IDENTIFIERS
```

A template cannot:

- carry live staging or production identifiers;
- become review-ready;
- contain lifecycle timestamps;
- be revoked or consumed;
- bind itself to a repository revision;
- issue a permit;
- authorize automatic apply;
- claim an external action.

A live packet must be created as a separate `SUBMISSION` artifact in a review branch.

## Independent readiness lanes

A submission has two statuses:

```text
staging_status
production_status
```

and two unresolved lists:

```text
unresolved_staging_identifiers
unresolved_production_identifiers
```

This permits the responsible intermediate state:

```text
staging_status: READY_FOR_OPERATOR_REVIEW
production_status: AWAITING_IDENTIFIERS
```

Production identifiers are not required to review an isolated staging packet.

## Revision and digest binding

The packet contains no `authorization_basis_revision`.

The evaluator receives the exact repository revision as an external input and emits:

```text
evaluated_revision
identifier_packet_digest
```

Any staging or production authorization receipt must match both values.

This removes circular packet-to-revision binding while preserving exact-revision authority.

## Immutable lifecycle

Each submission records:

```text
created_at
expires_at
supersedes_packet_id
revoked
revoked_at
revocation_reason
```

The complete lifecycle is part of the canonical packet digest. Changes create a different packet digest and therefore cannot silently preserve an existing permit.

Submission lifetime is limited by the evaluator to seven days.

## Independent consumption

Staging and production consumption are tracked separately:

```text
staging_consumption
production_consumption
```

Each lane is one of:

```text
UNUSED
CONSUMED
```

A consumed staging lane cannot be reused, but it does not automatically consume the production lane. A consumed production lane likewise does not rewrite staging history.

The committed template uses `NOT_APPLICABLE` for both lanes.

## Staging submission procedure

1. Copy the template into a branch-specific submission artifact.
2. Set `artifact_kind` to `SUBMISSION`.
3. Assign a unique `packet_id`.
4. Add creation and expiry timestamps.
5. Populate only verified non-secret staging references.
6. Set `staging_status` to `READY_FOR_OPERATOR_REVIEW`.
7. Empty only `unresolved_staging_identifiers`.
8. Leave production status and identifiers unresolved.
9. Preserve all safety fields.
10. Run strict validation, redaction scanning, focused tests, and full CI.
11. Obtain exact-head operator disposition.
12. Merge the packet only—issue no permit in the same PR.

Expected result:

```text
staging_packet_ready_for_review: true
production_packet_ready_for_review: false
staging_identity_authorization_effective: false
production_deployment_authorization_effective: false
```

## Permit separation

A staging permit remains a separate artifact, exact-revision and packet-digest bound, target bound, single-use, and valid for at most four hours.

A production permit remains separate and cannot become effective unless:

```text
readiness >= max(90, configured threshold)
production_ready == true
blocking_gaps == []
production release gate == PERMIT
source_revision == evaluated_revision
```

Packet readiness is not operational authority.

## Safety invariants

v1.1 fixes:

```text
raw_secret_values_present: false
operator_review_required: true
automatic_apply_allowed: false
external_action_performed: false
```

Raw secret values, service-account keys, tokens, passwords, test-user email addresses, and credential material are prohibited.

## Rollback

Before merge, close or abandon the branch.

After merge, revert the packet schema, template, evaluator schema, evaluator implementation, tests, and this runbook as one unit.

No cloud, provider, identity, secret, database, DNS, Terraform, deployment, or external-system rollback is required because this change performs no live action.
