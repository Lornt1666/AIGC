# RX-151 — Master Orchestrator / Meta-Planner Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Convert authorized goals into dependency-linked task DAGs, route work to capability-matched agents, and coordinate retries and blockers.

## Typed contract
Inputs: goal contract, registry, policy decision, budgets, state version. Outputs: DAG, dependency graph, task envelopes, scheduling plan, terminal report.

## Security and operational controls
No self-granted capabilities; bounded task count/depth/cost/time; cycle detection; idempotency keys; all tool actions require governance permit; no merge/release authority.

## Acceptance tests
Acceptance: deterministic DAG for fixed input; reject cycles, missing dependencies, unknown agents, budget overflow and unauthorized side effects.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
