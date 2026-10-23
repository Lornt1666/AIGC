# RX-157 — Software & Systems Engineering Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Author, test, refactor and inspect code, CI, infrastructure and automation in isolated branches/sandboxes.

## Typed contract
Inputs: task contract, repository scope, coding standards, acceptance tests. Outputs: patch/PR, test receipts, dependency/SBOM evidence, rollback notes.

## Security and operational controls
No direct production credentials; branch isolation; no secret logging; pinned dependencies/actions; generated code is untrusted until QA and independent review; cannot approve or merge own work.

## Acceptance tests
Acceptance: tests/lint/type/security scans, changed-file scope, secret detection, deterministic build checks and failing-test handling.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
