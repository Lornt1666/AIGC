# RX-152 — Governance & Policy Enforcement Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Evaluate proposed tool actions against authenticated policy, data boundaries, IAM scopes, budget/rate limits, and risk tiers before execution.

## Typed contract
Inputs: typed action request, signed policy version, agent identity, tool schema, risk tier, permits. Outputs: signed/structured ALLOW/DENY decision with policy version and reasons.

## Security and operational controls
Deny by default; policy inputs authenticated; least privilege; no policy mutation by workers; no bypass; separate policy author and enforcement identity; irreversible actions require human approval.

## Acceptance tests
Acceptance: negative policy suite covers unauthorized resource, expired/replayed permit, out-of-scope tool, budget limit, missing signature and policy version drift.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
