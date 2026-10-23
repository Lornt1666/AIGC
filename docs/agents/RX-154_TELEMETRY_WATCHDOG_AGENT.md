# RX-154 — Telemetry & Watchdog Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Monitor worker heartbeats, latency, failures, spend, retries and stuck tasks; alert, pause or fail-stop through approved control interfaces.

## Typed contract
Inputs: signed/structured spans, heartbeat stream, SLOs, budget policy, kill-switch state. Outputs: alerts, health state, bounded recovery recommendation, audit event.

## Security and operational controls
Watchdog cannot override governance or restart forbidden actions; hard ceilings; privacy minimization; monotonic event IDs; safe stop on missing telemetry or policy; recovery is idempotent.

## Acceptance tests
Acceptance: heartbeat loss, zombie worker, retry storm, spend cap, telemetry gap and kill-switch tests trigger deterministic stop/alert.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
