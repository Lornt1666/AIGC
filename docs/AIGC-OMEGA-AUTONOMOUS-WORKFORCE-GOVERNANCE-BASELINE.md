# AIGC–Ω Autonomous Workforce: Enforced Governance Baseline

**Status:** Design baseline and acceptance contract; not a claim of implementation or release approval  
**Date:** 2026-10-20  
**Applies to:** work-order ingestion, agent planning, tool execution, approvals, artifacts, storage, recovery, and release

## Decision

AIGC must be autonomous in completing bounded, reversible internal work—not autonomous in granting itself authority. The orchestrator may plan and propose. A separately enforced policy/execution boundary decides whether a requested operation is permitted. Unknown, expired, mismatched, or unverifiable conditions fail closed.

This document is a requirements baseline. A control is not considered implemented merely because it is described here, present in a prompt, or represented by a mocked test.

## Non-negotiable invariants

1. **Deny by default.** A missing, unknown, malformed, or unavailable policy decision denies the operation.
2. **No self-approval.** The proposing agent, executing agent, verifier, and release approver cannot impersonate the independent human authority.
3. **Approval binds to an immutable action.** Approval covers the normalized action digest, principal, tool/adapter, target resource, arguments, scope, risk tier, work-order/run ID, policy version, and expiry. Any material change invalidates approval.
4. **Authorize at execution time.** Re-check the permit immediately before the side effect; session-start approval is insufficient.
5. **Least privilege.** Every worker receives only task-scoped capabilities. Research/read-only workers have no write or execution tools. Unknown tools are unavailable.
6. **Untrusted input stays data.** Web pages, job posts, files, retrieved documents, agent messages, tool descriptions, and model outputs cannot amend policy or grant permission.
7. **No blind retry after ambiguous side effects.** Persist an operation intent before execution. If the outcome is uncertain, mark it `UNKNOWN`, reconcile by idempotency key/read-back, and do not replay blindly.
8. **Idempotent internal processing.** Stable work-order and operation keys prevent duplicate artifacts, events, payments, messages, or external actions.
9. **Evidence must be verifiable.** A success status requires independently checked postconditions and digests, not just a successful model response or process exit code.
10. **Audit is append-only to the application.** Normal agents cannot edit/delete audit history or silence the independent monitor.
11. **Emergency stop dominates.** Stop blocks new actions and invalidates outstanding permits; recovery requires explicit operator action and reconciliation of in-flight operations.
12. **Budgets are hard limits.** Enforce maximum wall time, steps, retries, tool calls, output bytes, concurrency, and spend outside model reasoning. Unknown/zero budget is interpreted conservatively; no paid provider or resource is enabled by default.
13. **Release is a separate human decision.** Passing CI or an agent-generated report never merges, deploys, or authorizes production activity by itself.

## Required action lifecycle

`RECEIVED → VALIDATED → PLANNED → POLICY_CHECKED → AWAITING_APPROVAL (if required) → PERMIT_ISSUED → EXECUTING → VERIFYING → SUCCEEDED | FAILED | UNKNOWN | BLOCKED`

- Every transition is persisted before the next irreversible boundary.
- A rejected or expired approval cannot be revived by changing a status field.
- A permit is short-lived, single-purpose, non-transferable, and replay-protected.
- `SUCCEEDED` requires independent verification of the expected state.
- `UNKNOWN` is a first-class terminal-for-automation outcome until reconciled by a permitted process or human.
- A cancellation/emergency stop cannot claim to reverse a side effect that already occurred; it blocks subsequent actions and triggers reconciliation.

## Evidence receipt contract

Each run receipt must include, at minimum:

- schema version, run ID, work-order ID, created/finished timestamps;
- source commit SHA and Git tree SHA for the code actually tested;
- canonical work-order digest and configuration/policy versions;
- ordered phase transitions and attempt numbers;
- each tool/action intent, normalized argument digest, policy decision, permit ID (never the secret token), and outcome;
- artifact paths/IDs, content digests, schema-validation outcomes, and independent postcondition results;
- test command, exit status, CI run URL, and exact tested SHA;
- explicit network/egress and external-action status, including how it was measured;
- unresolved warnings, unknown outcomes, skipped checks, and human-review state.

A receipt must never contain credentials, raw approval tokens, or unnecessary sensitive source text. A receipt is not evidence of an external action unless the destination state is independently verified.

## Acceptance matrix

| Scenario | Required result |
|---|---|
| No approval for a high-impact action | Block before adapter invocation; no side effect |
| Approval belongs to another action or changed arguments | Reject; require a new approval |
| Expired, malformed, revoked, or unverifiable permit | Deny |
| Agent asks for an unlisted tool or broader scope | Deny and audit |
| Prompt injection asks to reveal secrets, alter policy, or call a new destination | Treat as untrusted data; deny unauthorized action |
| Duplicate request / concurrent duplicate | One logical operation and stable receipt identity |
| Crash before operation intent is persisted | Safe restart without inferred execution |
| Crash after intent but before confirmed outcome | Reconcile; otherwise mark UNKNOWN, never blind-retry |
| Verifier reports mismatch or cannot run | No success state; quarantine artifact and escalate |
| Audit store unavailable | Block high-impact execution; do not silently bypass audit |
| Emergency stop is active | No new permit or action; in-flight work is reconciled |
| Budget or deadline exhausted | Stop safely, persist partial result and reason |
| Source revision changes after test | Prior receipt cannot satisfy exact-head acceptance |
| Agent proposes to approve its own work or release | Reject; require independent human authority |

## Test strategy

Use deterministic, synthetic fixtures and zero external side effects for default CI. At least one integration test must exercise the real existing application components from input to validated output; a test-only reimplementation or fully mocked pipeline does not qualify as end-to-end.

Separate suites should cover:

1. contract/schema and malformed-input validation;
2. action authorization and approval binding;
3. duplicate/concurrent idempotency;
4. restart and ambiguous-outcome recovery;
5. prompt injection, tool allowlist, secret redaction, and egress denial;
6. output schema, provenance, digest, and independent verification;
7. bounded retry, timeout, cancellation, emergency stop, and cost/step limits;
8. actual PostgreSQL/S3-compatible integration with isolated test resources and two independent workers;
9. release gates, exact-head binding, and reviewer independence.

Tests must assert negative properties (no adapter invocation, no network egress, no secret leakage, no success receipt) as well as positive outputs. Test failures cannot be suppressed by weakening the assertion in the same change without independent review.

## Deployment and operations requirements

- Separate read-only research, artifact-writing, and external-action identities/adapters.
- No long-lived production credentials in prompts, workspaces, agent environments, test fixtures, or logs. Prefer workload identity and short-lived scoped credentials.
- Apply network egress allowlists and sandboxing to code execution and browsing.
- Version policy and tool registries; pin dependencies and remote tool versions; review dependency and workflow changes.
- Keep monitoring and emergency-stop enforcement outside the agent's control.
- Define retention, redaction, incident response, backup/restore, key rotation, and credential revocation before production.
- Maintain explicit SLOs for completion latency, failure rate, unresolved UNKNOWN outcomes, approval latency, duplicate suppression, and spend per completed work order.

## External standards and reference guidance

- [Canadian Centre for Cyber Security: Careful adoption of agentic AI](https://www.cyber.gc.ca/en/guidance/careful-adoption-agentic-ai) — human oversight, controlled context, identity, risk-based permissions, output validation, and resource limits.
- [Microsoft Learn: Secure agentic systems](https://learn.microsoft.com/en-us/security/zero-trust/sfi/secure-agentic-systems) — least privilege, deterministic controls, transparency, human control, and supply-chain awareness.
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) — tool scoping, approval integrity, bounded loops, adversarial testing, and release gates.
- [OWASP DevSecOps AI Agent and MCP Security](https://github.com/OWASP/DevSecOpsGuideline/blob/master/current-version/2-Process/2-2-Develop/2-2-5-AI-Agent-and-MCP-Security.md) — deny-by-default tool policy, identity separation, and review of high-impact actions.

These sources inform the baseline; they do not certify AIGC or substitute for project-specific testing.

## Current known gaps and release decision

The existing focused CI evidence does not by itself demonstrate a complete durable vertical slice or real PostgreSQL/S3 recovery. The independent reviewer requirement remains open, and production release is not authorized. Track each acceptance item with a named test, exact revision, retained CI evidence, and a qualified human reviewer.

**Decision: NOT READY FOR RELEASE until every applicable gate is demonstrated and independently reviewed.**
