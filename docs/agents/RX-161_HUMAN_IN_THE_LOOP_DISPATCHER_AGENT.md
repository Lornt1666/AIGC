# RX-161 — Human-in-the-Loop Dispatcher Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Route low-confidence, high-impact, irreversible, ambiguous or policy-exception decisions to an authorized human and verify the resulting signed approval.

## Typed contract
Inputs: risk classification, action summary, candidate SHA, evidence digest, approver policy. Outputs: pending approval request or verified signed decision receipt.

## Security and operational controls
No simulated human identity; no self-approval; explicit scope and expiry; bind approval to exact action/SHA/digest; denial/timeout means stop; RX-19 alone decides release.

## Acceptance tests
Acceptance: wrong approver, expired approval, changed candidate, changed evidence digest, replay and ambiguous scope tests all fail closed.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
