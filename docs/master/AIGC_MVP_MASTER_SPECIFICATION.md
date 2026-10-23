# RegenExcalibur AIGC — MVP Master Specification

**Document class:** Master requirements and system specification  
**Version:** 1.0.0-draft  
**Status:** Proposed; not a production approval  
**Owner-designated principal:** Justice Gray Maciocha  
**Business/project identity:** RegenExcalibur  
**Product:** AIGC — Artificial Intelligence Gladiator Coliseum  
**Repository:** `Lornt1666/AIGC`  
**Release authority:** RX-19 under the current project governance  
**Release posture:** BLOCKED pending independently verifiable evidence  
**Default security posture:** deny by default; dry-run; read-only where possible; no external side effects without scoped authorization.

> This master specification states what the system is intended to do and how its components must connect. A requirement in this document is not proof that the implementation exists, is enabled, or has passed tests. Implementation status must be established from code, configuration, tests, CI, and operational evidence tied to an exact commit.

## 0. Document hierarchy and use

Read and apply documents in this order:

1. **This master specification** — mission, system boundaries, authoritative requirements, architecture, data flows, and design invariants.
2. **Wiring and interface registry** — each component connection, its contract, owner, failure behavior, and acceptance evidence.
3. **Operations, security, and recovery runbook** — how to validate, deploy to staging, observe, stop, recover, and roll back.
4. **Verification and production acceptance plan** — tests, fault injection, evidence requirements, and release gates.
5. **Governance and system charter** — identity, authority hierarchy, release decision authority, and change control.
6. **Existing code, schemas, registry, tests, and deployment files** — the implementation source of truth for current behavior. If docs and code disagree, record a discrepancy; do not assume either side is correct without investigation.

Recommended starting points:
- `docs/AIGC_GOVERNANCE_AND_SYSTEM_CHARTER.md`
- `docs/PRODUCTION_CLOSURE_ACCEPTANCE_MATRIX.md`
- `README.md`
- `src/aigc.py`
- `src/core/phase_registry.py`
- `schemas/`
- `tests/`

## 1. Identity, mission, and accountability

### 1.1 Identity

- **RegenExcalibur** is the business/project identity associated with this initiative. This is not a claim of incorporation, trademark registration, or other legal status.
- **Justice Gray Maciocha** is the owner-designated project principal. Repository permissions and legal ownership are separately verified facts.
- **AIGC** means Artificial Intelligence Gladiator Coliseum: a governed multi-agent application for intake, research, assessment, planning, proposal generation, approval, controlled operations, audit, outcome learning, and system verification.
- **RX-19** is the sole release decision authority under the current governance baseline.
- **RX-144** coordinates closure work but has no independent release authority.
- Agents and tools are subordinate to explicit contracts, authenticated policy, capability permits, human approval, and system safety controls.

### 1.2 Mission

AIGC should convert a well-defined task into an auditable, bounded, reviewable result by:
1. accepting a task and classifying its risk;
2. validating input and task contract;
3. selecting only registered and enabled capabilities;
4. scheduling work under deadlines, budgets, and hop limits;
5. routing messages through durable and recoverable interfaces;
6. persisting task state and audit evidence;
7. validating each artifact before downstream use;
8. requiring explicit authorization before protected side effects;
9. observing performance and security events without leaking secrets;
10. making outcomes reproducible enough to investigate and improve; and
11. preventing an agent from approving its own authority, bypassing policy, or authorizing production release.

### 1.3 What AIGC is not

- Not an unrestricted autonomous operator.
- Not permission to execute arbitrary model-generated Python or shell commands.
- Not a guarantee that all registered agents are implemented or enabled.
- Not a substitute for professional human judgment, qualified independent security review, legal review, or operational responsibility.
- Not a release-authorizing CI pipeline by itself.
- Not a source of legal claims about RegenExcalibur beyond verified records.
- Not a mechanism for converting untrusted retrieved text into instructions or permissions.

## 2. Epistemic discipline: how statements are classified

Every engineering status report must label claims as one of:

- **Observed fact:** directly read from a repository, test output, service, or authoritative source with timestamp and identity.
- **Verified behavior:** observed fact supported by reproducible acceptance tests against a specific code revision.
- **Calculated bound:** derived from stated assumptions and formulas, with units and limits.
- **Design requirement:** what the system must do; not a claim that it already does.
- **Assumption:** a temporary premise requiring validation.
- **Unknown:** unavailable or not yet verified.
- **Blocked/unverifiable:** evidence missing, stale, contradictory, inaccessible, unauthenticated, or not bound to the candidate.

Never promote “planned,” “documented,” “registered,” “mocked,” or “works locally” to “production-ready” without evidence.

## 3. System scope and lifecycle

AIGC is organized as a sequence of guarded phases. A phase is a component boundary, not a security boundary by itself. Each phase must declare:
- stable phase ID and version;
- purpose and risk tier;
- exact inputs and schemas;
- exact outputs and schemas;
- allowed data sources;
- permitted side effects;
- required identity and capabilities;
- deadline and resource budget;
- idempotency key and retry policy;
- audit events;
- failure states and recovery behavior;
- tests and acceptance criteria.

### 3.1 Phase map

| Phase / subsystem | Intended responsibility | Output / handoff | Hard boundary |
|---|---|---|---|
| Phase 2 — Opportunity Radar | Read approved public/API/RSS sources; normalize, classify, filter unsafe targets, score fit | Validated opportunity queue, raw source records, audit trail | Read-only; no applications, messages, bids, submissions, credential use, or employer contact |
| Phase 3 — Assessment | Analyze Phase 2 records and produce evidence-backed assessment dossiers | Dossiers with sources, confidence, assumptions, gaps, fit, risks | No external action; unsupported claims must be marked unknown |
| Phase 4 — Proposal Drafting | Draft tailored professional proposal packages from validated dossiers | Draft package with provenance and review status | Drafting is not sending; no claim may be invented to improve fit |
| Phase 5 — Human Approval Gate | Create an exact-action authorization packet with scope, target, risk, expiry, and approval requirements | Pending/approved/denied/revise decision record | Approval is action-specific, expiring, non-transferable, and not blanket consent |
| Phase 6 — Controlled Execution | Process only valid packets explicitly eligible for Phase 6 and produce exact-action receipts or manual handoffs | Receipt/manual handoff, result state, audit evidence | No packet or invalid/expired permit means no effect; unknown outcome must be reconciled before retry |
| Phase 7 — Employer-Safe Audit Packet | Assemble an internal audit packet safe for a prospective employer to review | Draft packet and redaction report | No external sharing by default; data minimization and human review required |
| Phase 8 — Outcome and Evolution Loop | Record outcomes, calculate agent performance, propose changes | Outcome ledger, performance records, patch proposals | Behavior-changing patches require review and explicit operator approval |
| Omega-X | Supervise local memory and evolution patch records | SQLite memory and append-only event records | Cannot change its own authority or write to external memory locations without explicit config and approval |
| Phase 11 — Secret Vault Scaffold | Validate secret references, broker access under policy, redact output, audit access | Secret references, non-secret access logs, command plans | Secret values must never be committed; live retrieval disabled by default |
| Phase 12 — Observability | Export a health snapshot and local dashboard | Snapshot and health report | Dashboard is not proof of telemetry coverage or production SLOs |
| Phase 13 — Simulation and replay | Run synthetic simulation and real public-data read-only replay | Simulation/replay result and report | Real replay stops before external action |
| Milestone A — Kernel CLI | Provide contract validation, state initialization, phase registry, unified CLI, status and validation | Consistent command surface and state | CLI routing is not authorization; each phase still enforces its own contract and permits |
| Phase 14 — Runtime preflight | Internal preflight for runtime readiness | Preflight result | No external action |
| Phases 15–17, 22–23 | Registered kernel/phase workflows | Defined by current phase registry and schemas | Do not infer behavior from phase number; inspect the authoritative registry and implementation |
| Closure workflow / RX-149+ | Gather evidence, verify, review, test, and prepare release decision | Evidence packet, blocker matrix, decision handoff | No release without RX-19's exact-candidate decision receipt |

**Important:** phase numbering and registry membership do not imply complete integration. For Phases 15–17 and 22–23, the source-of-truth phase registry and corresponding implementation must be inspected before declaring a function. The exact expected behavior, schemas, and side-effect class must be added to the Wiring Registry before these phases are production-enabled.

## 4. Core architecture

### 4.1 Recommended target: hybrid Saga-driven directed graph

Use a bounded coordinator and explicit directed task graph for policy and dependencies, event-driven transport for worker decoupling, durable state for correctness, and Saga-style compensation only for operations whose side effects and compensations are explicitly defined.

**Why this target:** a centralized-only controller can become a bottleneck and single point of failure; pure choreography makes end-to-end state, rollback, and causal tracing difficult. The hybrid approach keeps policy and task state explicit while allowing independently scalable workers.

### 4.2 Logical layers

1. **Ingress/API/CLI:** authenticate caller, validate payload size and schema, create request ID, apply rate limits, classify risk, and record initial audit event.
2. **Contract validation:** validate version, required fields, bounds, allowed enums, task scope, expiry, budgets, hop count, and idempotency key.
3. **Policy and permit service:** authenticate policy inputs; evaluate identity, role, scope, action, resource, expiry, risk tier, and human approval. Return a signed or otherwise authenticated permit; deny by default.
4. **Registry and scheduler:** select only enabled, versioned handlers; construct DAG; reject cycles or excessive depth; enforce concurrency and budget limits.
5. **Coordinator/state machine:** persist state transitions and outbox events transactionally; schedule retries and deadlines; reconcile uncertain outcomes; orchestrate Saga steps.
6. **Transport:** Redis Streams consumer groups or a reviewed equivalent; use explicit acknowledgement, pending-message inspection, reclaim, bounded retention, and dead-letter procedures.
7. **Workers/adapters:** validate message again, claim idempotency, verify permit at point of effect, run only the registered handler, bound resources, record result, and acknowledge only after durable completion.
8. **Static arbiter:** parse and inspect proposed source/payload without executing it; reject disallowed constructs and over-limit inputs. It is not a sandbox and must not authorize code execution.
9. **Persistence:** PostgreSQL is the intended durable system of record for production orchestration, outbox, receipts, and audit metadata. Existing SQLite stores remain local MVP components unless migrated and verified.
10. **Memory/retrieval:** ephemeral task context, optional vector retrieval, and durable transactional state remain separate. Retrieved content is untrusted data.
11. **Artifacts/evidence:** content-addressed artifacts, canonical manifests, schema validation, digest checks, source provenance, and retention policy.
12. **Observability:** OpenTelemetry traces/metrics/logs, redaction, health checks, dashboards, alert routing, and operational ownership.
13. **Human control plane:** approval/denial/revision, emergency stop, incident escalation, and release decision records.
14. **Release closure:** exact candidate readback, CI, independent review, supply-chain evidence, human acceptance, RX-19 decision, and post-check candidate re-read.

## 5. Data contracts and state transitions

### 5.1 Versioned contract envelope

Every inter-component message must carry, as applicable:
- `schema_name` and `schema_version`;
- `message_id` and stable `task_id`;
- `correlation_id`, `causation_id`, and trace context;
- producer identity, component version, and creation time;
- payload digest and content type;
- task deadline and resource budget;
- hop count and retry/attempt number;
- idempotency key;
- policy version and permit reference, if authorized;
- sensitivity/data classification;
- candidate SHA and evidence digest for release-closure artifacts.

Reject unknown major versions, malformed fields, unbounded strings/lists/nesting, expired deadlines, impossible hop counts, and payloads over configured byte limits. Backward-compatible minor changes must be explicit and tested.

### 5.2 Task state machine

Allowed conceptual states:
`RECEIVED → VALIDATED → QUEUED → RUNNING → SUCCEEDED`

Failure and review paths:
`REJECTED`, `WAITING_FOR_APPROVAL`, `RETRY_WAIT`, `RECONCILING`, `COMPENSATING`, `DEAD_LETTERED`, `CANCELLED`, `FAILED`, `NEEDS_OPERATOR`.

Rules:
- Every transition records actor, prior state, new state, timestamp, reason code, correlation ID, and contract/policy version.
- Illegal transitions are rejected.
- `SUCCEEDED` means required outputs were validated and durably recorded, not simply that a model returned text.
- A timeout after a possible side effect transitions to `RECONCILING`, not automatically to `FAILED` or retry.
- Compensation is a separate operation with its own authorization, idempotency key, evidence, and outcome.
- Emergency stop prevents new effects and dispatch; it must not erase or silently mutate already-recorded evidence.

### 5.3 Idempotency and zero-loss semantics

Do not promise “exactly once” across distributed services. Design for at-least-once delivery and idempotent effects:
1. Persist task/state and outbox event in one database transaction.
2. Publish outbox events; publication may repeat.
3. Consumer validates and claims idempotency key plus payload digest in durable storage.
4. Same key and same digest returns the prior result or resumes safe processing.
5. Same key with a different digest is a conflict and must be rejected.
6. Record effect result durably before acknowledging transport.
7. On uncertain external outcome, reconcile with the external system or escalate; never blindly repeat a non-idempotent action.

## 6. Reliability, latency, and budget controls

The prompt's numeric values are **initial targets**, not measured facts:
- queue latency target: p95 below 500 ms under a defined test load;
- per-agent processing timeout: 30 seconds by default, with explicitly configured exceptions;
- maximum hop count: 10;
- hard task and provider token/cost ceilings;
- bounded concurrency and payload sizes;
- finite retry count with exponential backoff and full jitter.

Specify SLOs by workload and environment. Define percentile, sampling window, offered load, payload distribution, provider, and failure conditions before claiming performance. Use a deadline budget across all hops; do not grant every downstream step a fresh full timeout.

Retries must:
- retry only transient and safe-to-repeat failures;
- stop at attempt/deadline/budget ceiling;
- use exponential backoff plus jitter;
- be rate-limited and circuit-broken;
- dead-letter poison payloads with reason and evidence;
- avoid retrying authorization, schema, policy, or integrity failures as transient.

## 7. Security and trust model

### 7.1 Trust boundaries

Treat all model output, retrieved documents, public feeds, queue messages, generated code, artifacts, plugin/tool responses, and worker output as untrusted until independently validated. Never treat instructions embedded in data as policy.

### 7.2 Mandatory controls

- authenticated service identities and least-privilege permissions;
- authorization at ingress and immediately before each protected effect;
- short-lived, scoped permits with resource/action constraints and replay prevention;
- secrets manager for secret values; repository stores references only;
- no secret values in prompts, logs, telemetry, artifacts, CI output, or exception messages;
- schema validation and payload bounds at every trust boundary;
- egress allowlists, network segmentation, and no public database/Redis exposure;
- non-root runtime, read-only filesystem where possible, CPU/memory/process limits, dropped capabilities, and restricted network;
- dependency pinning, full-SHA workflow action pins, image digests, SBOM, vulnerability scanning, provenance verification;
- independent security review and remediation evidence;
- data minimization, retention/deletion policy, and redaction;
- emergency-stop mechanism that is tested and cannot be cleared by an untrusted agent.

### 7.3 AST arbiter limitations

The AST arbiter may detect a subset of dangerous syntax, imports, dynamic execution patterns, excessive nesting, and oversized inputs. It cannot prove arbitrary code safe. It is not a substitute for a sandbox, OS isolation, container policy, seccomp/AppArmor/SELinux where available, resource limits, network restrictions, or an explicit decision to disable execution entirely. The safe MVP default is to inspect generated code as data and never execute it.

## 8. Persistence and memory

### 8.1 L1 ephemeral context
Task-local scratch state. It may be lost on crash and must never be the only record of approval, authorization, idempotency claims, or release evidence.

### 8.2 L2 retrieval/vector index
Optional retrieval store (Qdrant only if configured and tested). It accelerates semantic search; it is not the authoritative ledger. Every item must have source, timestamp, classification, retention, and access metadata. Retrieval results are untrusted and must be citation-grounded when used for factual claims.

### 8.3 L3 durable state
PostgreSQL is the target production system of record for tasks, state transitions, outbox, idempotency claims, permits/receipts metadata, audit references, and migration history. Local SQLite databases are valid for a local MVP only if limitations and backup requirements are explicit.

### 8.4 Append-only audit evidence
Audit events should be append-only at the application level, sequence-ordered, timestamped, linked by task/correlation IDs, and protected from ordinary worker modification. Hash chaining can make tampering detectable but does not authenticate the source or guarantee immutability. Use restricted roles, separate storage, signatures where required, retention controls, and independent verification.

## 9. Observability and operational outcomes

Emit trace spans across ingress, coordinator, queue, worker, adapter, persistence, and external dependencies. Metrics should include:
- request/queue latency distributions;
- queue depth and oldest pending age;
- task counts by state and phase;
- retries, dead letters, reclaims, duplicate claims, and conflict rejects;
- worker utilization, timeout rate, crash rate, and resource saturation;
- policy/permit denials and stale/replayed receipt rejections;
- provider latency, token/cost use, budget exhaustion, and circuit-breaker state;
- artifact validation and evidence closure outcomes;
- backup age, restore-test age, and replication/WAL status as applicable.

Logs must be structured, correlated, access-controlled, retention-limited, and redacted. Never label the system “healthy” from a process heartbeat alone; health must include dependencies, queue progress, durable writes, and critical synthetic checks.

## 10. Deployment target

### 10.1 Local MVP
Use a documented local configuration with clear dev-only defaults. SQLite is acceptable for single-user experiments; external actions remain disabled. Keep fake-secret tests and synthetic simulation separate from live credentials and public-data replay.

### 10.2 Staging target
Containerized app/API, worker, PostgreSQL, Redis Streams, and optional Qdrant on internal networks. Run as non-root, pin image digests, use health checks, resource limits, read-only root filesystems where feasible, isolated secrets, and persistent volumes with tested backup/restore. Staging must use synthetic or explicitly authorized low-risk data.

### 10.3 Production target
Only after all gates pass: managed or hardened PostgreSQL and Redis, controlled network and identity, secret manager, artifact registry, signed provenance, monitoring/alerting, backup/PITR, incident response, deployment rollback, and a named operational owner. The production target is not authorized by this document.

## 11. Acceptance rules

A component is accepted only when all relevant items are true:
- contract is defined and versioned;
- implementation is registered and its enablement state is explicit;
- positive, negative, boundary, and failure tests pass;
- unauthorized actions are proven blocked;
- observability and redaction tests pass;
- state and idempotency behavior survives injected failures;
- documentation and runbooks match the implementation;
- security review findings are closed or formally risk-accepted by the authorized role;
- evidence is bound to the exact commit and configuration.

System release requires the gates in `docs/PRODUCTION_CLOSURE_ACCEPTANCE_MATRIX.md` plus the verification plan. No one component's PASS overrides another gate's BLOCK.

## 12. Primary research and standards

- NIST AI RMF Generative AI Profile, AI 600-1: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- NIST Secure Software Development Framework, SP 800-218: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- SLSA provenance: https://slsa.dev/spec/v1.2/provenance
- SLSA verification: https://github.com/slsa-framework/slsa/blob/main/spec/verifying-artifacts.md
- GitHub artifact attestations: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- Redis Streams: https://redis.io/docs/latest/develop/data-types/stream/
- PostgreSQL backup and restore/PITR: https://www.postgresql.org/docs/current/backup.html
- OpenTelemetry signals: https://opentelemetry.io/docs/concepts/signals/

## 13. Change control

Any change to trust roots, permission tiers, side-effect adapters, release authority, evidence policy, persistence semantics, or enabled-agent status requires:
1. a versioned change request;
2. threat and failure-mode review;
3. updated contracts and tests;
4. independent review for security-sensitive changes;
5. exact-head CI;
6. migration and rollback plan where applicable;
7. owner/governance approval;
8. audit record and updated documentation.

This specification is a proposed baseline. It must not be represented as production certification or permission to deploy.
