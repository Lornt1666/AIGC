# AIGC MVP Master Control-to-Evidence Traceability Standard

**Document class:** Normative engineering control and acceptance standard  
**Version:** 1.0.0-draft  
**Status:** Proposed; review required; not production certification  
**Applies to:** Every AIGC phase, agent, adapter, queue, data store, policy, deployment artifact, and release decision  
**Release authority:** RX-19 under current project governance

## 1. Governing principle

**Standards guide the controls. Controls constrain runtime behavior. Tests challenge the controls. Operational evidence establishes what actually happened. An authorized release decision evaluates the complete evidence set.**

These layers are distinct and MUST NOT be substituted for one another:

1. **Standard / requirement:** normative statement of what must be true.
2. **Control:** design or enforcement mechanism intended to make the requirement true.
3. **Implementation:** concrete code, configuration, infrastructure, or human procedure.
4. **Verification test:** repeatable test of correct behavior, including negative and fault cases.
5. **Operational evidence:** attributable records of actual tested or deployed behavior.
6. **Acceptance decision:** authorized, candidate-specific decision weighing evidence, exceptions, residual risk, and release criteria.

A policy document does not prove enforcement. Code does not prove that a path is reached. A passing unit test does not prove deployment configuration. Green CI does not prove live dependency configuration. A dashboard does not prove telemetry completeness. A signed artifact does not prove safe behavior. Evidence must be scoped to the claim it supports.

## 2. Normative language and evidence labels

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative. Deviations from MUST/MUST NOT require an explicit, time-bounded risk exception from an authorized human; an agent cannot approve its own exception.

Every status claim must use one of these labels:

- **OBSERVED:** directly retrieved from a named source, with timestamp and source identity.
- **TESTED:** a repeatable test passed for an exact candidate and test configuration.
- **VERIFIED:** the required evidence set was reviewed independently against a stated acceptance criterion.
- **CALCULATED:** derived from stated inputs, assumptions, formula, units, and bounds.
- **REQUIRED:** intended behavior not yet proven.
- **ASSUMED:** temporary premise that must be validated.
- **UNKNOWN:** no adequate evidence is available.
- **BLOCKED:** missing, stale, contradictory, inaccessible, unauthenticated, incomplete, or candidate-mismatched evidence prevents acceptance.
- **EXCEPTED:** an authorized exception exists, with scope, rationale, owner, expiry, and compensating controls.

Do not use “production-ready,” “secure,” “reliable,” “integrated,” or “tested” without naming the exact claim and supporting evidence.

## 3. Requirement-to-evidence record

Each control requirement MUST have a durable record with these fields:

| Field | Required content |
|---|---|
| Requirement ID | Stable identifier; never recycled |
| Requirement | One testable normative statement |
| Risk / rationale | Harm or failure prevented |
| Source | Standard, threat model, business rule, or approved design decision |
| Control ID | Control(s) intended to enforce it |
| Control owner | Accountable role/team, not merely an agent name |
| Implementation reference | Exact file, function, configuration, infrastructure resource, or procedure |
| Enforcement point | Where control is applied, including point-of-effect checks |
| Verification | Positive, negative, boundary, adversarial, and recovery tests as appropriate |
| Operational evidence | Logs, traces, metrics, receipts, attestations, state snapshots, or human approvals |
| Freshness / binding | Candidate SHA, config digest, environment, test version, time window, and evidence digest |
| Acceptance criterion | Measurable pass/fail rule |
| Failure behavior | Fail-closed or explicitly justified safe degradation |
| Status | Label from Section 2 and implementation status from Section 12 |
| Exception / remediation | Owner, due date, expiry, compensating control, and closure proof |

A requirement without an implementation reference is a design requirement. A control without a test is unverified. A passing test without retained evidence is not auditable. An evidence record without candidate/environment binding cannot authorize release.

## 4. Required system ordering

1. **Define intent and risk:** caller, purpose, data classification, allowed and prohibited outcomes, risk tier, and human accountability.
2. **Validate ingress:** authenticate caller; enforce size, encoding, schema, rate, and content limits; reject malformed or ambiguous requests.
3. **Create task contract:** assign request/task IDs, contract version, idempotency key, deadline, token/cost ceiling, hop ceiling, allowed capabilities, and output expectations.
4. **Authenticate policy:** load policy from an authorized source, validate version and integrity, and reject missing, stale, malformed, or conflicting policy.
5. **Authorize exact action:** evaluate subject, role, action, resource, scope, expiry, environment, risk tier, and required human approval. No valid permit means no side effect.
6. **Resolve registry:** select only registered, versioned, enabled handlers; verify compatibility and policy; do not import arbitrary modules as a discovery side effect.
7. **Plan directed graph:** validate dependencies, detect cycles, cap fan-out/depth/hops, assign budgets, and identify compensation requirements before execution.
8. **Persist intent transactionally:** commit task state and an outbox event atomically where supported; never assume database commit and broker publish are one transaction.
9. **Deliver messages durably:** use versioned envelopes, stable message IDs, idempotency keys, explicit acknowledgement, pending-message recovery, bounded retries, and dead-letter handling.
10. **Revalidate at worker entry:** validate schema and policy again; verify task state, permit, deadline, budgets, replay status, and handler registration.
11. **Execute constrained handler:** isolate process/container/VM as appropriate to risk; apply OS-level identity, filesystem, network, CPU, memory, process, and time limits. Static AST inspection is supplemental and is not a sandbox.
12. **Commit result and audit evidence:** persist outcome and deduplication state before acknowledging delivery; record causal metadata without logging secrets.
13. **Verify outputs:** validate schema, provenance, policy compliance, and invariants before downstream use.
14. **Compensate or reconcile:** execute only predefined, tested compensation. If external outcome is uncertain, reconcile before retrying; do not blindly repeat non-idempotent actions.
15. **Observe and alert:** emit correlated structured logs, traces, metrics, security events, and audit records; alert on defined thresholds and missing telemetry.
16. **Close task:** produce final state, evidence digest, unresolved-risk list, and human-review requirement. “Completed” must not conceal partial, unknown, or compensated outcomes.
17. **Release separately:** build, test, review, attest, and accept the exact candidate; release remains a separate authorized decision.

Every stage failure must produce a defined state transition and safe response. Silent fallback, implicit permission, unbounded retry, and “success by timeout” are prohibited.

## 5. Logical wire contract

Every wire in the Wiring and Interface Registry MUST declare:

- **Producer and consumer:** versioned interface identifiers.
- **Purpose:** exact state transition or information transfer supported.
- **Envelope:** schema/version, message ID, task ID, correlation/trace context, timestamp, expiry, principal where relevant, and payload reference.
- **Payload contract:** types, required fields, size limits, allowed values, data classification, and validation rules.
- **Authorization requirements —** required identity, capability, permit scope, and point-of-effect revalidation.
- **Delivery semantics:** at-most-once, at-least-once, or another justified model. Do not claim exactly-once effects merely because a broker deduplicates messages.
- **Idempotency:** stable key, uniqueness scope, persistence duration, conflict behavior, and replay tests.
- **Ordering:** whether ordering matters and what key/partition establishes it.
- **Timeout and retry:** deadline, bounded attempts, exponential backoff with jitter, retryable error classes, and circuit-breaker behavior.
- **Failure path:** timeout, malformed message, unauthorized action, duplicate, poison payload, dependency outage, partial effect, and uncertain result.
- **Durability and recovery:** commit/ack order, pending-message reclaim, dead-letter policy, replay/reconciliation method, and retention.
- **Observability:** event names, metrics, trace propagation, audit fields, redaction rules, and alert thresholds.
- **Acceptance evidence:** tests and runtime artifacts proving each relevant property.
- **Status:** implementation status and exact evidence; a registry entry alone is not proof of a working wire.

For Redis Streams, consumers MUST account for pending entries, explicit acknowledgements, consumer-group recovery/reclaim, duplicate delivery, and dead-letter governance. For PostgreSQL, transaction boundaries and recovery claims MUST be validated against the actual schema, backup configuration, and restore exercises. Neither technology automatically creates a cross-system atomic transaction.

## 6. Architecture decision baseline

The target is a **hybrid, Saga-aware directed task graph**: an explicit coordinator and durable task state for policy/dependencies; event transport for decoupled worker delivery; and local, explicit compensation handlers for reversible operations. This is a design recommendation, not proof that the implementation matches it.

| Criterion | A — Centralized coordinator | B — Pure event choreography | C — Hybrid graph + event bus + Saga |
|---|---|---|---|
| Policy and dependency visibility | Strong | Weak to moderate; distributed | Strong |
| Single-controller dependency | High unless HA is engineered | Lower at coordinator layer | Moderate; coordinator must be recoverable |
| End-to-end traceability | Straightforward if instrumented | Harder; causal chains must be reconstructed | Strong if correlation/state transitions are enforced |
| Worker scaling | Moderate to strong | Strong | Strong |
| Cross-step compensation | Centralized but may become monolithic | Difficult to reason about globally | Explicit Saga plan and compensation records |
| Operational complexity | Lower initially; controller bottleneck risk | High distributed-debugging burden | Highest initial discipline; clearest policy/state model |
| Recommended use | Small bounded workflows | Independent event reactions with weak coupling | AIGC workflows requiring approval gates, durable state, and controlled effects |

Scores must be measured against representative workloads before production selection. Throughput, tail latency, recovery time, and cost cannot be inferred from this qualitative matrix.

## 7. Parameters and calculations

Initial values mentioned in project design—queue latency under 500 ms, worker timeout 30 seconds, and maximum hop count 10—are **proposed targets**, not measured SLOs. They remain provisional until benchmark, capacity model, workload profile, and authorized SLO review exist.

Every limit must specify unit and measurement point; hard maximum versus target percentile; workload and environment; safety margin; overload response; measurement source and alert; owner and review cadence.

A bounded retry policy may use: delay at attempt k = min(cap, base × 2^k) + bounded jitter. This is not complete until retryable errors, idempotency, maximum attempts, cumulative wait, deadline, and dead-letter disposition are defined. Cost controls must include provider/token ceilings, tool-call ceilings, wall-clock deadline, fan-out ceiling, and a global kill/circuit-breaker path.

## 8. Required controls, tests, and evidence

| Control domain | Required behavior | Minimum verification | Required evidence |
|---|---|---|---|
| Identity and authorization | Deny by default; least privilege; exact action/resource/scope; human approval for protected effects | Missing, expired, wrong-scope, revoked, forged, replayed permit tests | Auth decision, permit ID/digest, principal, policy version, result |
| Task contract | Versioned bounded schema; immutable identity; explicit budgets and expiry | Invalid schema, oversized payload, unsupported version, missing fields, boundary cases, deadline expiry | Validation result, contract version/digest, rejection reason |
| Registry and import | Discover metadata without executing untrusted code; only enabled handlers execute | Malicious import side-effect test, duplicate ID, disabled handler, incompatible version | Registry snapshot/digest, handler identity/version |
| Orchestration | Valid DAG, bounded hops/fan-out, durable transitions, deadline enforcement | Cycle, duplicate dispatch, controller restart, race, timeout, partial failure | State history, graph plan, task outcome |
| Messaging | At-least-once-safe processing, ack after durable outcome, bounded retries and DLQ | Crash before/after commit, duplicate delivery, lost ack, stale pending entry, poison loop | Message IDs, consumer-group state, attempts, DLQ disposition |
| Side-effect execution | Point-of-effect permit check, isolation, allowlisted adapters, idempotency or reconciliation | Prompt injection, path/network escape, privilege escalation, duplicate external request | Permit verification, sandbox profile, adapter receipt, reconciliation |
| Static arbiter | Bounded parse/inspection only; never treated as isolation | Node/depth/byte limits, syntax errors, forbidden constructs, adversarial Unicode | Decision, rule version, input digest, bounded failure result |
| Persistence and recovery | Transactional state, defined backup/restore, tested RPO/RTO | Database outage, corrupt backup, isolated restore, outbox replay | Backup verification, restore log, measured RPO/RTO |
| Secrets | References only in app state; scoped retrieval; redaction | Secret canary scan, unauthorized access, log leak, revoked credential | Secret-manager audit, redaction test, rotation evidence |
| Model/tool outputs | Retrieved text is untrusted data; provenance/schema validation; bounded tool use | Indirect prompt injection, malformed output, unsupported claims, unsafe arguments | Source provenance, validator output, tool invocation audit |
| Observability | Correlated traces, metrics, logs, audit trail; no sensitive payload leakage | Missing trace context, exporter outage, cardinality stress, secret redaction | Trace/metric/log samples, alert firing, telemetry health |
| Supply chain | Review dependencies/build; bind artifacts to source and build | Dependency policy, artifact tamper, provenance verification, secret scan | SBOM where required, build provenance/attestation, commit and artifact digest |
| Release governance | Exact candidate, complete CI, independent review, human acceptance, authorized release decision | Stale-success invalidation, changed SHA, missing reviewer, incomplete evidence | Candidate SHA, run IDs/attempts, reviewed SHA, acceptance digest, RX-19 decision |

## 9. Failure-mode analysis

For every high-risk path, record severity, likelihood, detectability, affected assets, existing controls, residual risk, owner, and test evidence. At minimum analyze:

1. Poison-pill loops and dead-letter bypass.
2. Duplicate delivery causing repeated external effects.
3. Crash between effect and result persistence.
4. Partial Saga completion and failed compensation.
5. Malicious or indirect prompt injection changing tool use.
6. Static analysis falsely interpreted as a sandbox.
7. Forged, stale, overbroad, or replayed permits.
8. Recursive plans exhausting cost, tokens, concurrency, or time.
9. Secret leakage through logs, exceptions, traces, or artifacts.
10. Stale CI success masking a newer failed/in-progress attempt.
11. Build artifact not corresponding to reviewed source.
12. Missing telemetry creating false confidence.
13. Backup that exists but cannot be restored.
14. Agent/policy self-modification bypassing operator approval.
15. Human approval attached to a different action, target, revision, or evidence digest.

High-severity unresolved findings block production. A compensating control must be documented, tested, owned, time-bounded, and approved by an authorized human.

## 10. Evidence quality and release binding

Evidence must be authentic, integrity-protected, relevant, complete, fresh, reproducible where feasible, independently evaluated where required, privacy-safe, and causally linked.

Release closure must bind at least: candidate commit SHA; tree/artifact digest; workflow IDs and latest attempts; test and security scan outputs; reviewer identity and reviewed SHA; human acceptance identity and reviewed SHA; evidence manifest and canonical digest; exceptions; and RX-19's decision. A later commit invalidates prior candidate-specific evidence unless applicability is explicitly demonstrated and the acceptance process rebinds the full set.

## 11. Production gate sequence

AIGC MUST NOT be called production-ready until all applicable gates pass:

1. **G0 — Scope and authority:** owners, allowed use, risk classification, release authority, prohibited actions.
2. **G1 — Requirements and traceability:** every critical requirement maps to controls, code/config, tests, evidence, and criteria.
3. **G2 — Contract and state correctness:** schemas, transitions, idempotency, concurrency, and migrations tested.
4. **G3 — Security:** threat model, authorization, isolation, prompt-injection defenses, secret handling, supply-chain controls, independent review.
5. **G4 — Reliability:** fault injection, queue recovery, crash consistency, compensation/reconciliation, backup restore, load tests.
6. **G5 — Observability:** alerts, dashboards, audit completeness, telemetry-loss behavior, incident procedures demonstrated.
7. **G6 — Operational readiness:** staging runbook, rollback, emergency stop, ownership, capacity limits, recovery exercise.
8. **G7 — Exact-head CI and provenance:** required workflows pass on the exact candidate; artifact/source linkage verified.
9. **G8 — Independent review and human acceptance:** findings remediated or explicitly excepted; acceptance bound to candidate and evidence digest.
10. **G9 — Release decision:** RX-19 records an explicit decision for the exact candidate and evidence digest. No agent or CI workflow may substitute for this decision.

A failed or unknown gate remains BLOCKED; do not average away a critical failure with high scores elsewhere.

## 12. Implementation status and change control

For each control, use one implementation status:

- IMPLEMENTED_AND_TESTED
- IMPLEMENTED_UNVERIFIED
- PARTIAL
- SPEC_ONLY
- DISABLED
- BLOCKED

“Implemented and tested” requires a concrete implementation reference and test run for an exact SHA. Production integration additionally requires runtime configuration and operational evidence. A fixture, mock, stub, example Compose file, or local-only pass is not proof of production integration.

Every change to a contract, policy, permit, state transition, retry rule, handler, dependency, deployment setting, or acceptance criterion MUST update this traceability record and regression tests. Re-run affected test layers and re-evaluate evidence freshness. Security-sensitive changes require independent review.

## 13. Standards and source basis

This document adapts recognized guidance; it does not claim formal certification or automatic compliance.

- NIST AI Risk Management Framework, Generative AI Profile: Govern, Map, Measure, Manage and lifecycle risk management. <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>
- NIST SP 800-218 SSDF and SSDF project material: secure-development practices across preparation, software protection, production, and vulnerability response. SP 800-218 Rev. 1 / SSDF 1.2 was listed as an initial public draft in December 2025, not a final standard. <https://csrc.nist.gov/pubs/sp/800/218/final> <https://csrc.nist.gov/pubs/sp/800/218/r1/ipd>
- OWASP Top 10 for Agentic Applications 2026: agent goal hijack, tool misuse, identity/privilege abuse, agentic supply-chain vulnerabilities, unexpected code execution, and related risks. <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>
- SLSA v1.2 provenance: verifiable information linking artifacts to where, when, and how they were produced. <https://slsa.dev/spec/v1.2/provenance>
- Redis Streams: consumer groups, pending entries, acknowledgements, reclaim/recovery, and delivery semantics. <https://redis.io/docs/latest/develop/data-types/stream/>
- PostgreSQL backup/recovery: recovery strategy must be validated through restore exercises. <https://www.postgresql.org/docs/current/backup.html>
- OpenTelemetry signals: correlate traces, metrics, and logs; telemetry presence alone does not prove completeness. <https://opentelemetry.io/docs/concepts/signals/>

## 14. Current disposition

This is a requirements and verification framework, not an attestation that AIGC currently satisfies it. The candidate remains blocked until repository inspection, executable tests, operational exercises, independent review, human acceptance, and RX-19's exact-candidate release decision provide the required evidence.


## 15. Documentation gate and operator-accountability controls

The master-document set is subject to deterministic structural validation by DOC-GATE-01, implemented as a candidate validator in `scripts/enforce_master_docs.py`. The AIGC CI workflow invokes the validator and its unit tests. This gate MUST fail closed for missing required documents, missing or duplicate W-001–W-045 identifiers, broken local Markdown links, absent audit-status safeguards, or missing legal/enforcement safeguard language.

The validator is intentionally not an LLM judge and does not execute content from documents. It cannot prove that a control is implemented in runtime code, that a legal term is enforceable, or that AIGC is production-ready. A successful run is structural evidence only and must be accompanied by source review, functional/security tests, operational evidence, independent review, human acceptance, and RX-19's release decision.

Operator accountability must be expressed as task-specific authorization and responsibility for the operator's own decisions, instructions, approvals, and conduct to the extent permitted by applicable law. It must not be written as a universal transfer of all liability or as a waiver of non-waivable rights. The draft acknowledgment in `AIGC_OPERATOR_RESPONSIBILITY_AND_AUTHORIZED_USE_ACKNOWLEDGMENT.md` requires qualified legal review and valid assent before adoption.

Evidence chain for the documentation gate:

1. Requirement/control ID and policy version.
2. Exact candidate SHA and workflow run/attempt.
3. Validator version and source digest.
4. Machine-readable validator output and exit code.
5. Focused test output bound to the same candidate.
6. Findings, remediation commits, and rerun evidence.
7. Independent acceptance of the full release evidence packet.

A subsequent commit invalidates the prior candidate's result for release acceptance. DOC-GATE-01 has no authority to waive findings, alter policies, approve a contract, enable an agent, merge a pull request, or release AIGC.


## 16. Saga authorization snapshot and point-of-effect controls

| Control ID | Required behavior | Implementation reference | Verification contract | Status rule |
|---|---|---|---|---|
| SAGA-AUTH-01 | Snapshot canonical JSON inputs before any awaited permit check; reject non-JSON, invalid Unicode, recursion failures, and payloads above 1,000,000 UTF-8 bytes | `core/orchestrator.py::SagaCoordinator.run_saga` | Mutate caller-owned nested mappings during async permit verification; prove adapter receives the exact snapshotted payload. Test invalid Unicode, circular input, non-finite values and oversized payload | `IMPLEMENTED_UNVERIFIED` until exact-head CI passes |
| SAGA-AUTH-02 | Bind the permit's input digest to the same canonical snapshot sent to the adapter | `core/orchestrator.py::SagaCoordinator.run_saga` | Compare verifier's input digest with the exact payload observed by the fake adapter; altered caller-owned data must not change execution bytes | `IMPLEMENTED_UNVERIFIED` until exact-head CI passes |
| SAGA-AUTH-03 | Reverify the permit immediately before every external adapter attempt, including retries | `core/orchestrator.py::SagaCoordinator._invoke_with_retry` via `before_attempt` | Expire/revoke authorization between preflight and dispatch and between retry attempts; adapter must not be invoked for a denied attempt | `IMPLEMENTED_UNVERIFIED` until exact-head CI passes |
| SAGA-AUTH-04 | Bind compensation authorization to the compensation payload and original action context; reverify on each compensation attempt | `core/orchestrator.py::SagaCoordinator._compensate` | Verify compensation payload digest and original payload digest; denial or expired permit must produce manual reconciliation and no compensation adapter call | `IMPLEMENTED_UNVERIFIED` until exact-head CI passes |
| SAGA-AUTH-05 | Ensure malformed or over-limit payloads fail before permit verification or any adapter call | `core/orchestrator.py::SagaCoordinator.run_saga` | Negative tests assert zero verifier and adapter invocations for invalid or oversized input | `IMPLEMENTED_UNVERIFIED` until exact-head CI passes |

The canonical snapshot is an authorization boundary, not a substitute for a sandbox. Only trusted, explicitly registered adapters may be invoked. Adapter contracts must still independently validate target resources, use least-privilege credentials, and provide outcome reconciliation for ambiguous remote effects.
