# RX-156 — Operations & API Action Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Perform approved, deterministic transactional operations through typed adapters with idempotency and reconciliation.

## Typed contract
Inputs: validated action contract, governance permit, target/resource, idempotency key, precondition snapshot. Outputs: transaction receipt, before/after state, reconciliation result.

## Security and operational controls
No write without signed permit; scoped service identity; idempotency keys; read-after-write reconciliation; two-phase/compensating workflow where supported; no destructive/financial/public actions without explicit human authorization.

## Acceptance tests
Acceptance: duplicate retry creates no duplicate side effect; timeout reconciliation; expired permit; resource mismatch; partial failure and rollback tests.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
