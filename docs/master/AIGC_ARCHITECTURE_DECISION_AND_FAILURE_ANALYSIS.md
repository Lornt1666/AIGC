# AIGC Architecture Decision, Reliability Bounds, and Failure Analysis

**Document ID:** AIGC-ADR-001  
**Version:** 1.0.0-draft  
**Status:** Proposed architecture decision; not a production certification  
**Applies to:** RegenExcalibur AIGC runtime, worker transport, policy boundary, evidence plane, and operational recovery  
**Decision owner:** Engineering; release decision remains RX-19  
**Current disposition:** Production blocked pending exact-head CI, runtime tests, security review, and operational evidence

## 1. Decision summary

Adopt a **hybrid Saga-driven directed graph**: a bounded coordinator enforces task contracts, policy and dependency order; PostgreSQL holds durable task/event/outbox/consumption/dead-letter state; Redis Streams provides at-least-once message transport; registered adapters perform explicitly allowlisted work; and an independent permit verifier gates protected effects. Use compensation only where the forward action and compensating action are explicitly defined, authorized, and operationally meaningful.

This is an architecture choice, not a claim that every layer is integrated or production-tested. Current `core/worker.py` is fail-closed and does not dispatch agents. No production authorization is granted.

## 2. Epistemic labels and bounds

Every value below is classified so a target cannot be mistaken for a measured result.

| Item | Value / rule | Classification | Verification required |
|---|---|---|---|
| Maximum task graph/Saga hops | 10 | Enforced code bound; candidate must pass tests | Boundary tests for 0, 10, 11 and malformed values |
| Default operation timeout | 30 seconds | Configured default, bounded by constructor validation | Deadline tests under contention, retry and reconciliation |
| Target queue latency | p95 under 500 ms | Proposed SLO, not measured | Declared load profile, repeated staging runs, p50/p95/p99 and sample size |
| Message delivery | At-least-once | Transport design property; duplicates expected | Crash-before-ack, duplicate-delivery and concurrent-consumer tests |
| Durable truth | PostgreSQL ledger/outbox | Design requirement | Commit/publish crash tests and restore/reconciliation drill |
| Redis Streams | Transport and pending-entry tracking | Component role | Redis outage, XAUTOCLAIM, trimming and poison-message tests |
| LLM/provider latency | Unknown until measured | Explicit unknown | Provider-specific latency and timeout distributions |
| External action duration/outcome | Unknown until target adapter is measured | Explicit unknown | Target-side receipt and read-after-write reconciliation |
| Agent enablement | All registry entries currently expected disabled/spec-only for reference worker | Current implementation boundary | Exact registry digest and startup test; no dynamic imports |
| AST policy | Static source screening only | Limited security signal | Adversarial test corpus; separate OS/container sandbox required |
| “Zero loss” | Not guaranteed by a queue choice alone | Prohibited blanket claim | Define recoverable failure model, durability settings, RPO/RTO and restore evidence |

### 2.1 Retry and deadline policy

For retry attempt index (k \geq 0), the current coordinator uses capped full jitter:

\[
d_k \sim U\left(0,\min(d_{max},d_0 2^k)\right)
\]

The retry loop uses one monotonic wall-clock deadline for the operation. A remote exception or timeout may occur after the target applied the effect; therefore retries are prohibited unless a trusted outcome reconciler proves `NOT_APPLIED`. `UNKNOWN`, reconciliation failure, permit denial, or deadline exhaustion must stop dispatch and produce a reconciliation/incident path. Idempotency keys are necessary but do not prove target outcome.

The action permit must be verified at preflight and again immediately before each adapter attempt. The payload digest used for authorization must be the digest of the same canonical snapshot passed to the adapter. The runtime bounds each forward and compensation payload to 1,000,000 UTF-8 bytes in the Saga entry path; other ingress paths must apply their own documented limits.

## 3. Architecture alternatives

Scores are comparative design judgments from 1 (weak) to 5 (strong) for this product's control requirements. They are not benchmark results and must not be presented as measured throughput or availability.

| Criterion | A — Centralized orchestrator | B — Pure event choreography | C — Hybrid Saga + directed graph |
|---|---:|---:|---:|
| Throughput / independent worker scale | 3 | 5 | 4 |
| Policy and state consistency | 5 | 2 | 4 |
| Compensation / rollback reasoning | 4 | 1 | 4 |
| End-to-end observability | 4 | 2 | 5 |
| Operational simplicity for small deployments | 4 | 2 | 3 |
| Failure isolation / graceful degradation | 2 | 4 | 4 |
| Human authorization enforcement | 5 | 2 | 5 |
| Overall fit for AIGC | 3 | 2 | **5** |

### 3.1 A — Centralized orchestrator

**Strengths:** one authoritative state machine; straightforward policy checks; simple causal trace and approval point.  
**Risks:** controller bottleneck and single failure domain; controller availability can halt progress.  
**Suitable when:** task volume is modest and consistency/audit are the dominant constraints.  
**Required mitigations:** durable state, restart/recovery, bounded queues, idempotent handlers, coordinator health alerts, and documented failover.

### 3.2 B — Pure event-driven choreography

**Strengths:** independent scaling, low coupling, natural event fan-out.  
**Risks:** distributed state is difficult to reconstruct; authorization can be fragmented; rollback and cycle detection are harder; poison events can cascade.  
**Suitable when:** domain boundaries are mature and independent teams can own their event contracts.  
**Required mitigations:** explicit event schemas, correlation/causation IDs, consumer idempotency, bounded hops, dead-letter policy, event ownership, and a central evidence view.

### 3.3 C — Hybrid Saga-driven directed graph (selected)

**Strengths:** explicit dependency graph and policy authority with event-driven transport; recoverable outbox; compensation and reconciliation can be traced to task/step IDs.  
**Risks:** more components and operational complexity; Saga compensation is not a database rollback and may fail; PostgreSQL/Redis consistency requires careful replay semantics.  
**Decision:** preferred because AIGC needs explicit human authorization, candidate-bound evidence, and auditable compensation without sacrificing worker decoupling.

## 4. System topology and interface responsibilities

| Layer | Responsibility | Must not do | Evidence / acceptance |
|---|---|---|---|
| Intake and contracts | Validate versioned TaskContract, idempotency, scope, risk, deadline, hop and budget limits | Dynamically import or execute agent code | Contract positive/negative tests; invalid input rejected before persistence |
| Registry and static inspection | Read data-only allowlisted agent metadata; inspect Python AST without executing it | Treat AST approval as sandboxing or agent activation | Registry integrity tests; import-side-effect test; adversarial AST corpus |
| Coordinator / DAG / Saga | Enforce dependencies, concurrency, deadlines, action permits, idempotency, compensation and state transitions | Authorize itself, skip permit checks, retry unknown outcomes | State-machine tests, point-of-effect tests, crash injection and exact event evidence |
| PostgreSQL ledger | Store task state, event sequence, outbox, consumed-event claims, dead-letter records and migration version | Permit runtime role to alter schema or rewrite immutable evidence | Least-privilege tests, transaction crash tests, append-only trigger tests, restore drill |
| Redis Streams | Deliver events at least once; track pending deliveries and consumer ownership | Be the only durable record of a task or external outcome | XPENDING/XAUTOCLAIM, duplicate delivery, trimming, outage and poison-message tests |
| Worker | Validate task, persist outcome, acknowledge only after durable processing | Execute disabled/spec-only agents or model-generated code | Disabled-agent rejection, ack-order tests, runtime identity and integration evidence |
| Action adapters | Call a small allowlist of external capabilities under exact permits | Expand scope, trust caller payload without validation, log secrets | Contract tests against fakes; target-side reconciliation; egress and credential isolation tests |
| Authorization verifier | Authenticate issuer/subject, signature, policy, candidate SHA, operation, resource, payload digest, audience and expiry | Accept caller-supplied `approved=true` or self-issued permission | Forgery, replay, expiry, wrong-scope, payload-mismatch and revocation tests |
| Evidence and telemetry | Bind events, traces, metrics and artifacts to task/candidate/policy; redact secrets | Treat logs or producer claims as authenticated proof | Trace propagation, digest validation, redaction tests, telemetry-loss behavior |
| Release gate | Aggregate exact-head CI, artifact provenance, review, human acceptance and RX-19 decision | Deploy, merge or certify by itself | Exact SHA/attempt/job checks and independent release decision receipt |

## 5. FMEA — Failure Modes and Effects Analysis

Severity and likelihood are qualitative initial ratings (High/Medium/Low), not statistically derived estimates. Any High severity failure blocks production until mitigation is tested and residual risk is accepted by an authorized independent reviewer.

| ID | Failure mode / effect | Detection | Required controls | Required evidence / release condition |
|---|---|---|---|---|
| FMEA-01 | Poison-pill event repeatedly crashes consumers; queue stalls | Delivery count, consumer errors, pending age, DLQ growth | Bounded retries; persistent DLQ record; alert; controlled replay with original identity and new replay authorization | Fault-injection proves bounded delivery, durable DLQ, no infinite loop, and replay audit |
| FMEA-02 | Crash after DB commit but before Redis publish | Unpublished outbox age | Transactional outbox; idempotent publisher; stable event ID | Kill process at commit/publish boundary; prove eventual publish without missing ledger event |
| FMEA-03 | Publish succeeds but acknowledgement/receipt is lost | Duplicate event ID; target receipt lookup | At-least-once semantics; consumer dedupe; target idempotency; reconciliation | Duplicate delivery test proves one logical state transition and no duplicate effect |
| FMEA-04 | Worker dies after external effect but before durable receipt | Unknown action outcome; adapter timeout | Read-after-write outcome reconciler; no retry on UNKNOWN | Simulated lost response proves no blind retry and explicit manual reconciliation |
| FMEA-05 | Saga step fails after earlier mutations | Saga state and incomplete compensation | Reverse-order compensation, separately authorized compensation operations, idempotency, reconciliation | Inject failure at every step; prove compensation order, records and manual escalation when incomplete |
| FMEA-06 | Compensation fails or is itself ambiguous | Compensation error/unknown state | Stop automated rollback; alert; retain per-step evidence; manual reconciliation | Inject compensation timeout; prove no false “rolled back” claim |
| FMEA-07 | Payload changes after permit preflight (TOCTOU) | Authorized digest differs from executed payload | Canonical payload snapshot before first await; byte cap; digest the snapshot; reverify at each effect/retry boundary | Mutate caller-owned nested mapping during async permit check; adapter must receive only the authorized snapshot |
| FMEA-08 | Permit expires or is revoked while waiting/retrying | Point-of-effect permit denial | Reverify immediately before every adapter attempt; bounded expiry; fail closed | Expiry/revocation between preflight and effect prevents adapter call |
| FMEA-09 | Forged or over-broad permit / confused deputy | Signature, audience, principal, policy or scope mismatch | Independent authenticated verifier; least privilege; exact target/action/digest binding | Forgery, wrong subject, wrong target, wrong policy and replay tests |
| FMEA-10 | Malicious source bypasses AST screening | Suspicious AST finding or sandbox escape attempt | AST is only a screening layer; separate OS/container sandbox; no secrets; deny network by default; syscall/resource limits | Sandbox escape red-team and egress tests before any generated code is enabled |
| FMEA-11 | Recursive task exhausts cost or resources | Token/cost budget, queue growth, CPU/memory and hop counters | Max hops, max attempts, absolute deadline, concurrency cap, per-task budget, circuit breaker and load shedding | Boundary and stress tests show bounded resource use under recursive/poison workloads |
| FMEA-12 | Redis trimming removes pending payload | XAUTOCLAIM deleted-entry report and DLQ record | PostgreSQL dead-letter ledger; no reliance on Redis-only retention | Trim pending entry in test; prove durable missing-entry disposition and alert |
| FMEA-13 | PostgreSQL outage or corrupted restore | Health checks, migration mismatch, failed consistency check | Tested backups, WAL/PITR where configured, migration validation, restore isolation, recovery runbook | Timed restore and ledger/outbox reconciliation against approved RPO/RTO |
| FMEA-14 | Secret leaks into logs, prompt, artifact or telemetry | Redaction scanner and secret canary | Secret references only, structured redaction, least-privilege identities, artifact scan | Canary secret remains absent from logs/artifacts; scanner must remain enabled |
| FMEA-15 | Stale or wrong-SHA CI/provenance accepted | Candidate SHA/run-attempt mismatch | Exact-head checks, required jobs, immutable artifact digest, provenance verification, independent acceptance | Prior success followed by new failure is rejected; changed SHA invalidates evidence |
| FMEA-16 | Operator acknowledgement is treated as blanket liability transfer | Legal review and policy audit | Task-specific informed assent; retain non-waivable rights/duties; legal review; audit operator's own approval | Counsel-reviewed text and tested acknowledgement-to-action binding before adoption |

## 6. Required invariants

1. **No permit, no protected effect.** Missing, invalid, expired, revoked, mismatched, or unverifiable authorization means no adapter invocation.
2. **Same bytes authorized and executed.** The permit digest must bind to a canonical payload snapshot used for that exact attempt.
3. **At-least-once is not exactly-once.** All transport consumers and external adapters need deduplication or reconciliation appropriate to the target.
4. **Unknown is not failure-to-apply.** Never retry an ambiguous side effect until the target outcome is reconciled as not applied or an explicitly reviewed idempotent replay rule applies.
5. **Compensation is a new side effect.** It requires its own authorization, bounded deadline, idempotency, evidence and outcome reconciliation; it does not erase prior effects.
6. **AST screening is not isolation.** No arbitrary agent/generated code is enabled based solely on a static AST report.
7. **Documentation is not evidence.** Every implementation claim must cite code, tests and exact-candidate operational evidence.
8. **Evidence is candidate-specific.** Any behavior-, policy-, dependency-, workflow- or configuration-relevant change invalidates affected acceptance evidence.
9. **Human acknowledgement is scoped.** An operator acknowledgment must not waive non-waivable rights or automatically transfer every party's legal responsibility.
10. **Release authority remains separate.** RX-19 is the sole release decision authority under the current project charter; CI and enforcement agents cannot self-release.

## 7. Acceptance sequence

1. Unit tests for contracts, snapshotting, permit binding, retry authorization, and state transitions.
2. Component integration with PostgreSQL and Redis, including duplicate and crash injection.
3. Adversarial authorization tests, including expired/revoked permits and payload mutation.
4. Runtime isolation review and proof that disabled agents cannot dispatch.
5. Dependency lock, immutable image digests, SBOM and provenance verification.
6. Staging load profile with queue-latency, timeout, cost and concurrency measurements.
7. Backup restore and recovery drill with approved RPO/RTO.
8. Independent security review and remediation against the exact candidate SHA.
9. Human acceptance of the exact candidate and canonical evidence digest.
10. RX-19 release decision; absent any required evidence, remain BLOCKED.

## 8. Research basis

This design is informed by:
- NIST AI RMF and the NIST Generative AI Profile for governance, risk mapping, measurement and management.
- OWASP Top 10 for Agentic Applications 2026 for agent-specific threats such as excessive agency, tool misuse, memory/prompt injection and weak inter-agent trust.
- Redis Streams documentation for consumer groups, pending-entry ownership, acknowledgements, XAUTOCLAIM and bounded dead-letter handling.
- PostgreSQL backup and restore documentation for logical dumps, physical backups and continuous archiving/PITR.
- SLSA provenance and GitHub artifact-attestation guidance for binding build claims to artifact identity and provenance; provenance is not a guarantee that the artifact is secure.

References:
- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- NIST GenAI Profile (NIST AI 600-1): https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- OWASP Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- Redis Streams: https://redis.io/docs/latest/develop/data-types/streams/
- PostgreSQL Backup and Restore: https://www.postgresql.org/docs/current/backup.html
- SLSA Provenance: https://slsa.dev/spec/v1.2/provenance
- GitHub Artifact Attestations: https://docs.github.com/en/actions/concepts/security/artifact-attestations

**Disposition:** Proposed decision record; runtime evidence remains pending. This document does not certify the system, grant legal advice, or authorize production deployment.
