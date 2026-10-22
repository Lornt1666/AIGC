# AIGC Governed Runtime Harness v0.1

**Status:** experimental reference implementation; not production integrated  
**Release authority:** RX-19 only  
**Default posture:** deny execution unless contract, agent enablement, scope, policy version, and authenticated permit verification all pass.

## What is wired

- **Versioned task contracts:** TaskContract validates the supported contract version, required identifiers, declared scope, exclusions, acceptance criteria, tool allowlist, and risk tier.
- **Authenticated tool permits:** PermitBroker denies by default if no verifier is configured. An adapter must provide a trusted permit_verifier that validates the permit's cryptographic signature and issuer authorization. The included test verifier is a test fixture only, not cryptography.
- **Least-privilege checks:** the agent must be explicitly enabled; the tool must be listed in the task contract; permit task/agent, tool, action, resource, and policy version must match exactly; permits expire and have bounded use counts.
- **Replay / identity guard:** permit IDs are bound to a canonical fingerprint in the in-memory process, so a reused ID with changed contents is denied.
- **Deterministic workflow state machine:** invalid transitions block; terminal states cannot restart; repeated event IDs are idempotently ignored.
- **Audit event digesting:** events and evaluation reports have deterministic SHA-256 digests over canonical JSON.
- **Reproducible local evaluation harness:** cases are sorted by stable case ID; duplicate/missing IDs block; results include pass/fail counts and a digest.

## Explicit limits and production blockers

This is a reference harness, not a distributed agent runtime. It does **not** execute tools, provide durable storage, verify signatures itself, issue permits, authenticate humans, enforce repository permissions, or authorize releases.

Before any production use, the implementation must be extended and independently reviewed for:

1. A production-grade, trusted permit issuer and cryptographic verifier with key rotation, issuer allowlists, revocation, canonical signed payloads, and fail-closed key-service outage behavior.
2. Durable transactional state and audit storage with concurrency control, uniqueness constraints, retention policy, tamper evidence, backup/restore, and independent evidence retention.
3. Adapter-side enforcement immediately before tool invocation; a decision returned by this library alone cannot prevent another code path from bypassing it.
4. Atomic permit consumption coordinated with invocation intent and outcome, including crash recovery and idempotency keys for external tools.
5. Strict runtime schema validation, maximum payload/resource limits, secret redaction, tenant isolation, and safe handling of untrusted tool output.
6. A real test matrix for concurrency, process restart, clock skew, policy revocation, malformed signatures, replay, timeout, cancellation, retries, partial failures, and adapter bypass.
7. Authenticated human review/acceptance receipts tied to the exact commit and evidence-manifest digest. A chat statement or test fixture is not an approval receipt.
8. End-to-end tracing, metrics, SLOs, alerts, incident playbooks, and rollback/recovery drills.
9. Independent security review and explicit human acceptance before release. RX-19 remains the sole release decision authority.

## Local validation

Run from repository root:

```bash
python -m pytest -q tests/test_aigc_governed_runtime.py
python -m pytest -q
```

The first command is a focused regression test. The second is the full repository suite. Record the exact commit SHA, commands, exit codes, test counts, and artifact digests in CI; never carry a passing result forward to a later commit.

## Acceptance criteria for this milestone

- Unknown contract versions and agents are rejected.
- Disabled agents, missing/unconfigured/invalid authenticators, expired permits, tool/scope mismatches, and policy mismatches are denied.
- A verified narrow permit authorizes only its declared scope and bounded use count.
- Workflow transitions are deterministic; replay is idempotent; invalid transitions are rejected.
- Evaluation output is stable for the same cases independent of input ordering.
- Tests run in CI on the exact PR head.
- No production authorization or release approval is inferred from these results.
