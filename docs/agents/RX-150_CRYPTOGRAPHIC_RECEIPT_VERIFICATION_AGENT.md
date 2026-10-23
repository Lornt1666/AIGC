# RX-150 — Cryptographic Receipt Verification Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Verify signed external evidence receipts and provenance claims against independently managed trusted issuer/key policy.

## Typed contract
Inputs: receipt envelope, purpose, expected SHA/digest/repository/workflow bindings, trusted keyset, revocation policy. Outputs: signature verification receipt, verified claims, key/issuer/purpose, receipt digest, rejection reason.

## Security and operational controls
Ed25519/Sigstore or equivalent approved verifier; strict canonicalization; key rotation/revocation; validity windows; anti-replay; algorithm allowlist; never trust a key embedded only in the receipt; never equate a valid signature with authorization unless trust policy says so.

## Acceptance tests
Acceptance: valid signatures pass; tampering, wrong key, revoked/expired key, wrong purpose, stale SHA, digest mismatch, replay, malformed envelope and unsupported algorithms fail closed.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
