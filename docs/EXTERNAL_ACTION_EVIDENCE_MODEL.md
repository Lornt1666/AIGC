# AIGC External Action Evidence Model

An external action is never represented by a reusable global permission.

## Admission prerequisites

Before execution, the connector must prove:

- approved connector identity and immutable version;
- accepted platform or automation policy;
- exact action type;
- exact destination;
- canonical payload bytes and SHA-256 digest;
- accountable operator identity;
- unexpired, single-use approval nonce;
- emergency stop is clear;
- idempotency key is unused;
- replay protection is active;
- credential reference is approved and resolved outside the repository.

## Immutable success receipt

```text
receipt_id
action_id
connector_id
connector_version
action_type
destination
payload_sha256
approval_id
approval_nonce_digest
operator_id
idempotency_key
started_at
completed_at
provider_result_reference
provider_result_digest
replay_rejected
external_action_performed=true
operator_review_required=true
```

The receipt proves only the exact action it describes. It cannot authorize another payload, destination, connector, employer, message, application, schedule, or deliverable.

## Failure or uncertainty

A failed or indeterminate attempt records:

```text
external_action_performed=false
outcome=FAILED | INDETERMINATE
operator_review_required=true
```

A retry is prohibited unless the connector's idempotency contract proves it safe and the approval policy explicitly permits it.

## Aggregate program truth

After one exact action receipt is integrity-verified and operator-accepted, the aggregate program may record:

```text
external_action_receipt_present=true
```

That aggregate truth is evidence of the control path. It is not permission for future external action.
