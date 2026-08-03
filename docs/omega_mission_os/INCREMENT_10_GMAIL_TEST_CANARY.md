# Ω Mission OS Increment 10 — Governed Gmail Test Canary

## Purpose

Increment 10 defines the one-action ceremony used to validate the Increment 8 gateway and Increment 9 Gmail adapter against a dedicated test account. It does not enable production and contains no email-send capability.

## Required human actions

Google OAuth consent and provider-side grant revocation require explicit operator interaction. The repository cannot silently authorize or revoke a Google account.

## Ceremony

1. Create a dedicated Gmail test account.
2. Normalize the address and calculate its SHA-256 fingerprint.
3. Generate a short-lived TEST activation record.
4. Keep the emergency stop enabled.
5. Configure the runtime credential outside the repository.
6. Authorize exactly one controlled self-addressed draft.
7. Unlock the emergency stop for the bounded canary only.
8. Create one draft with the fixed canary subject and body.
9. Read the draft back and verify recipient, subject, body, and `sent=false`.
10. Remove the local runtime credential.
11. Re-enable the emergency stop in a `finally` path.
12. Revoke the Google OAuth grant separately and record evidence.
13. Write the digest-protected canary receipt and append-only audit evidence.
14. End at `CANARY_VERIFIED_NOT_PRODUCTION_ENABLED`.

## Safety invariants

- The ceremony must begin and end with the emergency stop enabled.
- Provider identity must match the dedicated test-account fingerprint.
- The draft is addressed only to the same test account.
- One completed canary cannot be replayed for the same test account.
- Provider read-back must prove the draft is unsent.
- Local credential removal and provider OAuth revocation are distinct controls.
- Production activation remains false in configuration, activation records, receipts, and audit evidence.
- Audit records are append-only and SHA-256 hash chained.
- Provider draft identifiers are stored only as hashes.
- No send, reply, forward, update, delete, label, payment, or generic connector method is added.

## Live-use boundary

Merging this increment does not conduct a live canary. A live run requires a dedicated test Gmail account, explicit OAuth consent, a configured runtime credential, and an operator-supplied provider revocation evidence reference. Until those exist, the connector remains disabled.
