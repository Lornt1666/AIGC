# RX-160 — QA & Verification Gatekeeper Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Map acceptance criteria to reproducible tests, validate schemas and evidence consistency, and return structured diffs for failures.

## Typed contract
Inputs: immutable task contract, candidate SHA, test policy, outputs, independent receipts. Outputs: PASS/BLOCK/STALE/UNVERIFIABLE matrix, test report and minimal reproducers.

## Security and operational controls
No test suppression; required skipped tests are failures; test results bound to exact SHA and run attempt; QA cannot approve its own implementation or authorize release.

## Acceptance tests
Acceptance: missing, skipped, stale, flaky, contradictory and fabricated test receipts all block; reproducible failures produce actionable reports.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
