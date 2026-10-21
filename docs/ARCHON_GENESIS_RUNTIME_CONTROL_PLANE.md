# ARCHON-GENESIS Runtime Control Plane — Reference Implementation

**Status: isolated test reference; not production-ready.**

This increment provides a versioned task contract, service-principal identity labels, explicit tool allowlists, capability checks, task budgets, bounded retries, per-agent circuit breakers, async timeouts, cooperative cancellation, idempotency, health status, and a tamper-evident in-memory audit chain.

## Safety invariants
- The runtime is not an authorization provider and cannot mint or elevate credentials.
- Agent handlers receive only registered tools; unknown agents, contract versions, tools, and over-budget tasks fail closed.
- Self-requests are blocked; handler output cannot convey release approval or authority.
- The canonical Release Assurance Agent remains the sole release decision authority.
- Task payloads are data, not policy. Do not place secrets in payloads or logs.
- No merge, deployment, financial transaction, external outreach, or production release is performed.

## Required before production
1. Replace in-memory state with durable, authenticated services and a persistent audit store.
2. Bind service principals to workload identities; enforce mTLS and audience-scoped credentials.
3. Execute handlers in separate OS/container sandboxes with CPU, memory, filesystem, egress, and syscall restrictions.
4. Use a durable queue and process supervisor. Async timeouts cannot safely terminate hostile synchronous/native code; cooperative cancellation is not a hard kill.
5. Export audit records to access-controlled append-only storage with externally anchored signatures and retention.
6. Add a durable global budget ledger, tenant isolation, rate limits, and persistent circuit state.
7. Add deployment manifests, image provenance, SBOM, vulnerability scans, staged rollout, rollback, and independent security review.
8. Provision 25 service identities and separate deployments only after each agent has a concrete handler, interface contract, owner, tests, and operational SLOs.

This module intentionally does not create 25 pretend production agents. It supplies a shared runtime boundary for separately implemented handlers.
