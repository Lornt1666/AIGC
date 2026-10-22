# AIGC Runtime Maturity Process — RX-121–RX-126

**Status:** staged implementation in review; not production authorized  
**Canonical release authority:** RX-19 only  
**Default disposition:** BLOCK  
**Principle:** implement, validate, independently review, and authorize each gate before proceeding to the next gate. Later gates may be designed in parallel, but may not be declared passed while an upstream gate is unresolved.

## Agent assignments

| Agent | Role | Authority |
|---|---|---|
| RX-121 | Cryptographic Permit Trust and Key Lifecycle | R0, evidence and recommendations only |
| RX-122 | Durable Transactional State and Replay Integrity | R0, evidence and recommendations only |
| RX-123 | Tool Adapter Enforcement and Recovery | R0, evidence and recommendations only |
| RX-124 | Runtime Observability and Reproducible Evaluation | R0, evidence and recommendations only |
| RX-125 | Independent Runtime Security Assurance and Evidence Gate | R0, cannot impersonate or replace an independent human reviewer |
| RX-126 | Runtime Maturity Sequence and Gate Orchestrator | R0, coordinates only; cannot enable agents or authorize release |

All six agents remain disabled and specification-only. This is intentional: no registry edit can itself establish production readiness or safely activate an agent.

## Ordered process

### Gate 1 — Cryptographic trust (RX-121)

1. Define the canonical permit claim set, issuer identity, key ID, audience/tool, task, agent, action, resource, policy version, issue/expiry times, use count, and approval reference.
2. Verify EdDSA-signed permit tokens against a trusted issuer allowlist and public-key registry.
3. Support key rotation with overlapping ACTIVE and VERIFY_ONLY keys; explicitly revoke compromised keys and individual permit IDs.
4. Deny unknown issuers/keys, revoked permits/keys, invalid signatures, invalid audiences, malformed claims, expired permits, and key-service failures.
5. Run positive, negative, key-rotation, revocation, expiry, wrong-audience, and outage tests.
6. Persist key ID, issuer ID, policy version, decision reason, and evidence digest without logging private key material or bearer tokens.

**Current reference implementation:** src/aigc_runtime/permit_trust.py verifies EdDSA JWT permits against configured trusted issuers and keys, including key status and revocation lists. It does not issue tokens or retrieve keys from a KMS. Production trust-store loading, issuer governance, and revocation freshness remain blockers.

**Exit evidence:** exact commit-bound test report, trust-store version/digest, negative-test coverage, key-rotation and revocation evidence, and independent review.

### Gate 2 — Durability and concurrency (RX-122)

1. Replace in-memory audit and permit-use counters with transactional persistence.
2. Atomically consume permit use counts and reject permit-ID reuse with a different fingerprint.
3. Enforce idempotency-key uniqueness and reject a key reused for a different request digest.
4. Persist invocation state transitions and outcomes; an interrupted RUNNING invocation is UNKNOWN until reconciled, never blindly replayed.
5. Test parallel requests, process restart, transaction rollback, disk/database failure, backup/restore, and evidence retrieval.

**Current reference implementation:** src/aigc_runtime/durable_store.py provides a SQLite prototype with WAL/full-sync settings for file-backed databases, transactional permit-use and invocation records, and audit events. It is not a multi-node production database; production deployment needs managed PostgreSQL or an equivalent durable transactional service, migration controls, operational backup/restore, and independently retained audit evidence.

**Exit evidence:** concurrency and restart test reports, database schema/migration digest, recovery drill, retention/retrieval proof, and independent review.

### Gate 3 — Tool adapter enforcement and recovery (RX-123)

1. Inventory every real tool/MCP/provider adapter and all paths that can invoke it.
2. Route every invocation through the broker immediately before execution; deny direct/bypass paths.
3. Match the task, agent, tool, action, resource, policy version, issuer, and permit scope exactly.
4. Require idempotency keys and record intent/outcome. Never retry an uncertain external side effect without tool-specific reconciliation.
5. Test unauthorized calls, adapter bypass, duplicate requests, timeouts, partial completion, cancellation, retries, and crashes before/after the external side effect.
6. Keep production credentials and connector secrets outside source control and test fixtures.

**Current reference implementation:** src/aigc_runtime/tool_adapter.py calls the broker before a supplied handler and uses durable idempotency state to avoid repeating completed calls. It is not yet wired to every production adapter, and process-crash ambiguity still requires tool-specific reconciliation.

**Exit evidence:** adapter inventory, coverage map proving no bypass path, adapter contract tests, side-effect/idempotency evidence, and independent review.

### Gate 4 — Observability and reproducible evaluation (RX-124)

1. Emit correlated structured spans for task, agent, tool, policy decision, and workflow state.
2. Measure latency distributions, success/failure/block counts, policy-denial reasons, retry/recovery outcomes, and cost/quota where available.
3. Establish privacy-safe redaction and tenant boundaries before exporting telemetry.
4. Version evaluation datasets, prompts, model/provider, policies, tools, and test code; hash the manifest and result.
5. Require deterministic baseline cases, adversarial tests, regression thresholds, alert-delivery checks, and recovery-test evidence.
6. Set explicit SLOs and operational ownership before production traffic.

**Current reference implementation:** src/aigc_runtime/telemetry.py records structured local spans and basic latency/status/denial metrics. It is not an OpenTelemetry exporter, production metrics backend, alerting system, or cost meter.

**Exit evidence:** versioned evaluation manifest/results, trace samples, redaction tests, metric/alert checks, SLO proposal, and recovery-test report.

### Gate 5 — Independent assurance (RX-125)

1. Assign a qualified independent human reviewer through an authorized repository administrator; an AI agent cannot create the identity or substitute for that reviewer.
2. Bind findings to the exact reviewed commit and evidence manifest; track remediation and evidence-backed retesting.
3. Obtain complete CI for the exact final head and inspect the test logs/artifacts. Any new commit invalidates dependent evidence.
4. Verify repository protection and required checks through authorized administrator readback.
5. Obtain authenticated human acceptance bound to the exact commit SHA and evidence digest. Chat intent, a checkbox, or an agent-generated record is not sufficient.
6. Verify post-merge signed provenance/attestation and independently retained artifacts.
7. Send the complete evidence packet to RX-19 for the sole release decision.

**Exit evidence:** independent review identity/assignment, finding closure and retest records, exact-head CI/artifacts, protection readback, authenticated acceptance receipt, provenance verification, and successful independent retrieval of retained evidence.

## Activation and handoff rules

- Do not enable any of RX-121–RX-126 merely because their specification exists.
- Activate only the minimum required agent after its code is implemented, contract/negative tests pass, dependencies are satisfied, an independent review passes, rollback is tested, and an authorized human records activation.
- Start in a non-production isolated environment. Use test keys and synthetic resources in tests; never commit private keys or live bearer permits.
- Gate 2 may be prototyped after the Gate 1 interface is fixed, but cannot be accepted until Gate 1 trust semantics are agreed and tested.
- Gate 3 cannot be marked complete until the actual adapter inventory is covered.
- Gate 4 cannot be marked complete until telemetry is connected to real adapter paths and redaction/alert tests pass.
- Gate 5 cannot be marked complete without real independent human and administrator evidence.
- Any commit, policy, key, adapter, dependency, evaluation, or deployment change invalidates the affected downstream evidence.
- Missing, stale, contradictory, unauthorized, or unverifiable evidence means BLOCK.
- RX-126 sequences and reports; it cannot change gate criteria or mark a gate passed without evidence.
- RX-19 remains the sole release decision authority. Production authorization remains false until the complete evidence chain and explicit human approval are verified.
