# PR-EPI-02 ToolBroker Contract

## Status

`CONTRACT_ONLY — LIVE TOOL EXECUTION DISABLED`

## Purpose

PR-EPI-02 introduces a default-deny authorization and idempotency boundary for epistemic tool intents. It does not introduce a tool adapter, live dispatch mechanism, credential resolver, repository-writing agent, deployment path, or production activation path.

## Governing invariants

1. A policy permit is not evidence of tool execution.
2. A policy permit is not external-action authority.
3. Human approval is necessary where policy requires it, but approval alone is not sufficient for external execution.
4. Tool intents are bound to an exact repository revision and canonical request digest.
5. The idempotency key is the canonical request digest, excluding approval metadata and the key itself.
6. Duplicate intents are reported as `DUPLICATE_INTENT`, never as successful execution.
7. An idempotency-key collision with a different request fails closed as `IDEMPOTENCY_CONFLICT`.
8. Raw secret material is forbidden from tool request parameters.
9. Emergency stop, request budgets, and cost-unit budgets are evaluated before an idempotency claim is admitted.
10. The broker has no production in-memory idempotency default; a durable atomic ledger must be injected by a future governed integration.
11. Every decision receipt emitted by this slice records `external_action_performed=false` and `production_activation_authorized=false`.
12. No tool adapter is called by this slice.

## Decision semantics

- `DENIED`: policy or governance check failed.
- `APPROVAL_REQUIRED`: the intent is halted pending a separately bound human approval.
- `POLICY_PERMIT_PENDING_EXECUTION_GATE`: policy checks passed; this does **not** authorize or perform execution.
- `DUPLICATE_INTENT`: an identical request digest already holds the idempotency claim.
- `IDEMPOTENCY_CONFLICT`: the same key is associated with a different request digest.

## Future execution boundary

Any future adapter must be a separate governed increment and must validate the immutable ToolBroker decision, exact revision, authorization/approval evidence, emergency-stop state, rate and budget state, credential isolation, and durable idempotency state immediately before execution. It must issue an independent execution receipt after the attempted external action.
