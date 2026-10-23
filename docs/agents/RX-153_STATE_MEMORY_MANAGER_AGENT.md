# RX-153 — State & Memory Manager Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Maintain durable, versioned task state, episodic project events, and curated semantic memory outside model context windows.

## Typed contract
Inputs: typed events, task state transitions, access labels, retention policy. Outputs: versioned state snapshot, append-only event refs, retrieval results with provenance.

## Security and operational controls
Append-only event history; optimistic concurrency; tenant/project isolation; encryption and retention; no secret retention; memory writes schema-validated and access-controlled; LLM context is not the system of record.

## Acceptance tests
Acceptance: restart recovery, concurrent update conflict, tampered event, unauthorized read/write, retention deletion and replay tests.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
