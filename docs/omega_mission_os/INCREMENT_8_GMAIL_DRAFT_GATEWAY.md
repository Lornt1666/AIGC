# Ω Mission OS Increment 8 — Governed Gmail Draft Gateway

## Scope

Increment 8 introduces one reversible external capability: creating and verifying a Gmail draft from an exact `PREPARED_NOT_EXECUTED` packet.

It does not send email. It does not expose a generic connector executor. It does not accept arbitrary commands, URLs, providers, or action types.

## Required chain

1. Verified execution packet.
2. Verified second-stage `PREPARED_NOT_EXECUTED` approval.
3. One-time third-stage approval bound to the packet and payload digests.
4. Valid, disabled emergency-stop state.
5. Explicitly injected Gmail draft provider.
6. Provider creation response.
7. Provider read-back verification.
8. Hash-chained `DRAFT_CREATED_NOT_SENT` receipt.

## Fail-closed controls

- Missing, malformed, or enabled emergency stop blocks execution.
- Missing provider blocks execution.
- Ledger corruption blocks reads and appends.
- Reused packet or nonce blocks third-stage approval.
- Idempotent retries return the original receipt without creating another draft.
- Provider responses lacking a draft ID remain unsuccessful.
- A created object that cannot be read back with matching recipient, subject, body, and `sent=false` is rejected.

## Credential isolation

The provider is dependency-injected. OAuth access and refresh credentials remain in the connector secret store and are not accepted by, written to, or returned from the gateway contracts. Receipts contain only an account fingerprint and hashes of destination and provider object ID.

## Durable emergency stop

The checked-in example is locked by default. Production operation must use a runtime-local copy controlled independently from the repository. The stop is checked immediately before the provider call and its revision is captured in the receipt.

## Authority boundary

Allowed:

- `GMAIL`
- `CREATE_DRAFT`
- terminal state `DRAFT_CREATED_NOT_SENT`

Prohibited:

- send, reply, forward, delete, archive, label, or modify messages;
- non-Gmail connectors;
- contract acceptance;
- invoice or payment actions;
- Quest transitions;
- canonical-state mutation.
