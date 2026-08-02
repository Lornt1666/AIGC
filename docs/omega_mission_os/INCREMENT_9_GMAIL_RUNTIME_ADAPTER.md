# Ω Mission OS Increment 9 — Governed Gmail Runtime Adapter

## Purpose

Increment 9 provides a production-oriented Gmail provider implementation for the Increment 8 draft-only gateway. It remains disabled by default and exposes no send method.

## OAuth constraint

Google does not publish a general Gmail OAuth scope that permits `users.drafts.create` while cryptographically excluding `users.drafts.send`. Draft creation requires `gmail.compose`, `gmail.modify`, or full-mail scope. This implementation requests exactly `gmail.compose`, rejects `gmail.send`, `gmail.modify`, and full-mail scopes, and enforces the no-send boundary in code, routing, tests, approvals, and emergency-stop governance.

## Controls

- Disabled-by-default runtime configuration.
- Dedicated test-account mode.
- Exact normalized-email SHA-256 account fingerprint.
- Environment-only credential resolution; credentials are not accepted in API payloads or written to records.
- Fixed Google API endpoints for profile, draft creation, and draft retrieval only.
- No send, update, delete, list, modify, label, reply, or forward method.
- Account health check before draft creation.
- Provider read-back through `drafts.get?format=raw`.
- Governed activation record requiring `send_capability_present=false` and emergency-stop use.
- Non-test activation requires a verified test-account canary receipt.
- Credential-gated status, health, and local revocation API routes.

## Activation sequence

1. Create a dedicated Gmail test account.
2. Calculate the SHA-256 fingerprint of the normalized account email.
3. Store the access credential only in the configured runtime environment/secret provider.
4. Keep the connector disabled.
5. Record a bounded activation receipt for the test account.
6. Unlock the separate Increment 8 emergency stop for one controlled action.
7. Create one draft addressed back to the test account through the Increment 8 gateway.
8. Verify recipient, subject, body, account fingerprint, unsent state, idempotency, and receipt chains.
9. Revoke the credential and record the canary receipt.
10. Require separate human authorization before any non-test account configuration.

## Authority boundary

The adapter can call only:

- `users.getProfile`
- `users.drafts.create`
- `users.drafts.get`

It contains no Gmail send method, no `/send` endpoint, no generic HTTP target supplied by callers, and no canonical-state mutation.
