# AIGC Wiring and Interface Registry

**Version:** 1.0.0-draft  
**Status:** Proposed; implementation coverage requires repository-by-repository verification.  
**Purpose:** Define what each logical wire carries, who may use it, how failure is handled, and what proves the connection works.

## 1. What “wiring” means

A wire is a defined interaction between two components. Every wire must specify:
- producer and consumer;
- purpose and allowed operation;
- request/event schema and version;
- authentication and authorization;
- durable state and idempotency behavior;
- timeout, retry, and failure semantics;
- telemetry and audit events;
- acceptance tests;
- whether the wire is implemented, partially implemented, simulated, planned, or unknown.

A Python import, phase registry entry, environment variable, Docker network, or successful health endpoint is not by itself proof of a complete functional wire.

## 2. Canonical wire inventory

| Wire ID | Producer → Consumer | What it must do | Required failure behavior |
|---|---|---|---|
| W-001 | User/UI/CLI → Ingress | Accept a bounded task; authenticate caller; assign IDs; validate schema and risk | Reject malformed/oversized/unauthorized request; emit audit reason |
| W-002 | Ingress → Contract Validator | Validate version, required fields, enums, limits, data classification, expiry | Fail closed; no downstream dispatch |
| W-003 | Contract Validator → Policy/Permit Verifier | Request authorization for exact actor/action/resource/scope | Deny on missing, invalid, stale, revoked, or ambiguous policy |
| W-004 | Policy Verifier → Coordinator | Return authenticated decision/permit metadata, not arbitrary free-text authority | Invalid signature/issuer/purpose/scope must block |
| W-005 | Coordinator → Phase/Agent Registry | Resolve a named, versioned handler and enablement status | Unknown or disabled handler is rejected, not dynamically imported/executed |
| W-006 | Coordinator → Durable State/Outbox | Atomically persist task transition and outbox event | Transaction rollback on failure; no event published for uncommitted state |
| W-007 | Outbox Publisher → Redis Streams | Publish durable events with stable event ID and payload digest | Retry boundedly; duplicates tolerated; pending outbox remains visible |
| W-008 | Redis Consumer Group → Worker | Deliver work with message ID, task ID, correlation/trace context, attempt, deadline | Recover pending work after consumer loss; never assume one delivery |
| W-009 | Worker → Schema/Policy Revalidation | Revalidate message and current permit before processing/effect | Reject poison/stale/unauthorized event; bounded DLQ route |
| W-010 | Worker → Idempotency Ledger | Claim operation key and canonical payload digest | Same key/different digest conflict; concurrent duplicate claims serialize |
| W-011 | Worker → Tool Adapter | Invoke one allowlisted operation under least privilege | No permit or unsupported operation means no effect; timeout triggers reconciliation |
| W-012 | Tool Adapter → External Service | Perform exactly the scoped action approved by permit | Record request/response metadata without secrets; uncertain result becomes RECONCILING |
| W-013 | Worker/Adapter → Durable Result Store | Commit validated result, effect receipt, state transition, and audit references | No success acknowledgement before durable result |
| W-014 | Worker → Redis ACK | Acknowledge only after durable terminal result or durable transfer to retry/DLQ state | Crash before ACK yields safe redelivery; duplicate effect prevented by ledger |
| W-015 | Coordinator → Retry Scheduler | Schedule transient safe-to-repeat failure with bounded backoff | No retries for schema, authorization, integrity, or policy failures |
| W-016 | Retry Scheduler → DLQ/Operator Queue | Isolate poison or exhausted work with reason and replay metadata | No infinite redelivery; replay requires controlled operator action |
| W-017 | Saga Coordinator → Compensation Handler | Reconcile prior effects and invoke explicit compensating action | Never compensate based only on timeout; ambiguous outcomes escalate |
| W-018 | Artifact Producer → Artifact Validator | Validate schema, size, file set, content digest, manifest and provenance | Reject malformed archive, traversal paths, digest mismatch, unexpected files |
| W-019 | Artifact Validator → Downstream Phase | Provide validated immutable artifact reference plus digest | Downstream must recheck digest and schema; no mutable path-only trust |
| W-020 | Agent → Memory Retrieval | Query only permitted data partitions and classifications | Unauthorized records filtered; retrieved instructions treated as untrusted content |
| W-021 | Memory/Indexer → Durable Metadata | Store source, timestamp, classification, retention, digest, and ACL metadata | Incomplete provenance prevents publication/indexing |
| W-022 | Phase → Audit Ledger | Record start, end, decision, state transition, inputs/outputs digest, errors | Audit write failure blocks high-risk side effects; low-risk behavior must be explicit |
| W-023 | App/Worker → OpenTelemetry | Propagate trace context and emit bounded metrics/logs | Telemetry outage must not leak secrets; critical audit ledger remains distinct |
| W-024 | Secret Broker → Secret Manager | Resolve a referenced secret only for authenticated permitted caller and approved purpose | Deny by default; no secret value in logs; no live access in fake-test mode |
| W-025 | Phase 5 → Human Approval | Present exact action, target, scope, consequences, expiry, evidence | No ambiguous/blanket approval; denial/revision/expiry must be persisted |
| W-026 | Human Approval → Phase 6 | Provide authenticated approval bound to exact action digest and expiry | Approval cannot be reused for changed target/payload or after expiry |
| W-027 | Phase 6 → Execution Receipt | Produce exact action/result/time/actor/target/status evidence | Unknown outcome marked ambiguous and reconciled; never fabricate success |
| W-028 | Phase 8 → Evolution Review | Propose a versioned patch based on measured outcomes | Proposal cannot self-apply; behavior changes require review, tests, approval |
| W-029 | Omega-X → Local Memory/Events | Persist local memory/events under explicit path and retention policy | Do not write external memory path by default; protect against malformed event |
| W-030 | Phase 12 → Health Snapshot/Dashboard | Aggregate health and metrics with timestamps and source identity | Stale/missing data shown as unknown, not green |
| W-031 | Phase 13 Replay → Public Sources | Fetch approved public/API/RSS data in read-only mode | Respect rate limits, schema, timeout, data minimization; no writes/submissions |
| W-032 | Unified CLI → Phase Registry | Resolve phase ID to command, input/output, schema, mode, risk | Unknown phase or mismatched mode is rejected |
| W-033 | CLI Emergency Stop → Runtime Gate | Persist stop state and block new protected actions | Fail-safe on inability to verify stop state; clear requires authorized actor |
| W-034 | Closure Controller → GitHub Evidence Sources | Read PR, head/base, CI attempts/jobs/logs/artifacts/reviews/rulesets | Incomplete pagination or inaccessible source = UNVERIFIABLE |
| W-035 | GitHub Evidence → Canonical Evidence Packet | Normalize records, preserve raw provenance, calculate canonical digest | Conflicts/staleness block; never merge unrelated SHA evidence |
| W-036 | CI → Artifact/Provenance Verifier | Bind successful run attempt to artifact subject, trusted builder, parameters | Earlier success cannot override newer failed/in-progress attempt |
| W-037 | Independent Reviewer → Findings Ledger | Record reviewer identity, exact SHA, findings, severity, remediation evidence | Unassigned or non-independent review blocks release |
| W-038 | Human Acceptance → Closure Controller | Record authenticated acceptance for candidate SHA and evidence digest | Acceptance invalidated if SHA/digest changes |
| W-039 | Closure Controller → RX-19 | Deliver complete gate matrix and evidence digest | No incomplete packet; RX-144 may coordinate but cannot decide release |
| W-040 | RX-19 → Release Record | Record authenticated approve/reject/defer decision bound to exact candidate and digest | No release unless decision is valid and every prerequisite gate passes |
| W-041 | Deployment Controller → Environment | Deploy a verified immutable artifact through approved pipeline | No manual image tag substitution; rollback target and health verification required |
| W-042 | Backup System → Recovery Environment | Restore durable state and verify consistency in isolation | Never overwrite production during a drill; failed reconciliation blocks return to service |
| W-043 | Alerting → On-call/Owner | Route actionable alert with severity, runbook, owner, and correlation IDs | Alert delivery failure monitored; critical alerts have fallback route |
| W-044 | Policy Change → Runtime Policy Cache | Publish authenticated, versioned policy and revoke stale cache | Stale policy or revocation uncertainty blocks protected effects |
| W-045 | External Outcome → Reconciliation Worker | Compare intended effect, external state, and recorded receipt | Unresolvable mismatch enters NEEDS_OPERATOR; never guess |

## 3. Wire contract rules

### 3.1 Common envelope

Use a versioned envelope with these fields when relevant:
```json
{
  "schema_name": "aigc.task",
  "schema_version": "1.0.0",
  "message_id": "stable-unique-id",
  "task_id": "stable-task-id",
  "correlation_id": "request-correlation-id",
  "causation_id": "prior-message-id",
  "producer": {"component": "registered-name", "version": "immutable-version"},
  "created_at": "RFC3339 UTC timestamp",
  "deadline_at": "RFC3339 UTC timestamp",
  "hop_count": 0,
  "attempt": 1,
  "idempotency_key": "stable-operation-key",
  "payload_sha256": "hex-digest-of-canonical-payload",
  "policy_version": "policy-version",
  "trace_context": {"traceparent": "W3C trace context"},
  "data_classification": "internal",
  "payload": {}
}
```

This is an illustrative contract shape, not a statement that the repository currently implements this exact JSON. The schema must be versioned in the repository and validated at both producer and consumer.

### 3.2 Security rules at every wire

- Validate producer identity; do not trust a self-reported agent name alone.
- Validate payload bytes before parsing and nested complexity after parsing.
- Use canonical serialization for digests; define normalization rules.
- Check task deadline, policy version, permit expiry, and revocation immediately before protected effects.
- Never carry secret values in queue messages; carry a scoped secret reference only where necessary.
- Bind audit, result, and artifact to stable task/correlation IDs.
- Do not expose internal stack traces, secret-bearing request bodies, or unrestricted personal data in logs.
- Use a distinct service identity per trust boundary and least-privilege database roles.

## 4. Core subsystem responsibilities

### 4.1 Ingress and contract validator
**Must:** reject malformed input before work is scheduled; normalize only documented fields; preserve source provenance; attach request/task IDs.  
**Must not:** execute code, trust client-supplied role claims, or infer authorization from valid schema.  
**Acceptance:** malformed, oversized, unknown-version, and expired requests produce deterministic rejection with no downstream side effect.

### 4.2 Registry and scheduler
**Must:** resolve only statically registered handlers; check enabled state and compatibility; detect cycles; enforce concurrency, hop, deadline, and cost limits.  
**Must not:** import arbitrary module paths supplied by a model or execute arbitrary strings.  
**Acceptance:** disabled and unknown handlers cannot be dispatched; cyclic graph and budget-exhaustion tests pass.

### 4.3 Coordinator and Saga
**Must:** own explicit state transitions, dependency ordering, timeouts, retry decisions, compensation plans, and reconciliation.  
**Must not:** interpret timeout as proof that a side effect failed or blindly replay a non-idempotent operation.  
**Acceptance:** crash injection at every transition recovers to a known state without duplicate external effects.

### 4.4 PostgreSQL and outbox
**Must:** atomically commit task transition and outbox event; enforce unique idempotency constraints; retain audit references; support tested backup/restore.  
**Must not:** rely on Redis alone for the only copy of a critical task or permit.  
**Acceptance:** process crash between commit and publish causes eventual delivery; duplicate publish is safe; restore passes reconciliation.

### 4.5 Redis Streams
**Must:** distribute work, track pending messages, acknowledge after durable processing, reclaim abandoned work, and route exhausted poison messages to a controlled DLQ.  
**Must not:** be described as exactly-once execution.  
**Acceptance:** consumer crash, duplicate delivery, pending reclaim, stream trimming, and Redis outage tests pass. Redis retention/trim configuration must preserve all unprocessed work.

### 4.6 Worker and tool adapter
**Must:** handle one registered operation at a time within budgets; verify permit at the point of effect; validate tool output; record durable receipt.  
**Must not:** provide arbitrary shell, unrestricted filesystem, or unrestricted network access to the model.  
**Acceptance:** unauthorized operation attempts are denied and logged; timeouts enter reconciliation; secrets do not appear in outputs.

### 4.7 Static arbiter
**Must:** reject known-dangerous syntax and bounded-resource violations as preflight.  
**Must not:** claim code is safe or execute code.  
**Acceptance:** adversarial corpus tests include imports, dynamic execution, dunder access, resource exhaustion constructs, Unicode edge cases, huge ASTs, malformed syntax, and evasion attempts. A clean AST result never grants a runtime permit.

### 4.8 Artifact and evidence verifier
**Must:** verify exact bytes, archive safety, expected files, manifest digest, provenance subject, signer identity, workflow identity, and candidate binding.  
**Must not:** trust an artifact name, URL, status string, or producer-supplied `verified=true` flag.  
**Acceptance:** byte tampering, path traversal, stale artifact, wrong SHA, wrong signer, missing page, conflicting run attempt, and manifest mismatch all block.

### 4.9 Policy and permit service
**Must:** take authenticated policy inputs and evaluate principal, role, action, resource, environment, expiry, risk, and human approval; return a decision with provenance.  
**Must not:** rely on prompts, model output, local unsigned JSON, or a coordinator's assertion as authorization.  
**Acceptance:** deny-by-default, expiry, revocation, wrong audience, wrong action, wrong resource, replay, policy-version mismatch, and concurrent claim tests pass.

### 4.10 Human approval and release
**Must:** show the precise action, target, payload digest, consequences, scope, expiry, and reversal limits; record authenticated identity and decision.  
**Must not:** infer consent from silence or reuse approval after the payload changes.  
**Acceptance:** changed target/payload invalidates approval; approval expiry blocks execution; RX-19 receipt binds to exact candidate and evidence digest.

### 4.11 Memory and retrieval
**Must:** preserve source attribution and classification; enforce access controls; keep retrieval separate from system-of-record state.  
**Must not:** allow retrieved text to override policy or authorize tools.  
**Acceptance:** prompt-injection documents, cross-tenant records, expired records, and missing provenance are safely rejected or clearly marked.

### 4.12 Observability
**Must:** propagate trace context; expose meaningful queue/task/worker/security/backup metrics; redact sensitive attributes.  
**Must not:** log tokens, credentials, full sensitive payloads, or raw secret-manager responses.  
**Acceptance:** synthetic alert, trace continuity, redaction, metric cardinality, and telemetry outage tests pass.

## 5. Agent registry expectations

RX-149–RX-161 are intended roles, not automatically live agents:

| ID | Intended role | Input | Output | Required guard |
|---|---|---|---|---|
| RX-149 | Live GitHub Evidence Acquisition | Repository, PR, candidate context | Timestamped read-only source records | GET-only; pagination completeness; exact SHA |
| RX-150 | Cryptographic Receipt Verification | Receipt bytes, trust policy | Verified/rejected receipt and reason | Trusted issuer, purpose, expiry, revocation, replay claim |
| RX-151 | Master Orchestrator / Meta-Planner | Validated task and graph | Bounded plan | No privilege elevation; cycle/hop/budget controls |
| RX-152 | Governance / Policy Enforcement | Authenticated policy and action request | Permit/deny decision | Independent verifier; fail closed |
| RX-153 | State / Memory Manager | Authorized state operation | State update or retrieval result | No audit rewrite; access control and provenance |
| RX-154 | Telemetry / Watchdog | Runtime events and health | Alerts and health findings | Redaction; cannot override policy |
| RX-155 | Research / Evidence Synthesis | Questions and authorized sources | Cited evidence synthesis with uncertainty | No invented citations; separate facts/assumptions |
| RX-156 | Operations / API Actions | Permit and allowlisted operation | Result/receipt | No permit, no side effect |
| RX-157 | Software / Systems Engineering | Issue/spec/repo context | Patch proposal, tests, build artifacts | Exact-head CI and review required |
| RX-158 | Data Extraction / Analytics | Authorized dataset | Validated structured data/analysis | Schema, minimization, data scope |
| RX-159 | Adversarial Red Team / Security Auditor | Threat model and target revision | Findings and reproducible tests | Independent from implementation approval |
| RX-160 | QA / Verification Gatekeeper | Acceptance matrix and evidence | Gate-by-gate result | Cannot waive missing evidence or self-certify |
| RX-161 | Human-in-the-Loop Dispatcher | Decision request | Routed request and authenticated receipt | Cannot impersonate human or infer consent |

Each role requires a manifest containing immutable implementation version, enabled flag, input/output schema, permissions, identity, budget, deadline, tests, owner, and operational status. Disabled/spec-only means the dispatcher must refuse to schedule it.

## 6. Explicit unknowns to resolve before production

- Exact implemented behavior and contracts of Phases 15–17 and 22–23.
- Which components currently use SQLite versus PostgreSQL, and whether a production migration exists.
- Whether Redis Streams and Qdrant are wired into live runtime or only target architecture.
- Whether permit verification is cryptographic and independently trusted or only local policy logic.
- Whether the tool adapter actually enforces network, filesystem, shell, and provider limits.
- Whether telemetry spans cross all real runtime boundaries and alerts have been exercised.
- Whether dependency locks, image digests, SBOM, and verified provenance are enforced in CI.
- Whether branch protection, required reviews, CODEOWNERS, and deployment environments have been independently read back.
- Whether backup restore, RPO/RTO, disaster recovery, and incident response have been demonstrated.
- Whether the complete exact-head CI and independent security review have passed for the final candidate.

Every unknown must have an owner, test/evidence request, due date or priority, and a closure state. Until then, affected capability remains disabled or non-production.

## 7. Acceptance summary

A wire is complete only when:
1. its producer and consumer are known;
2. the schema and version are committed;
3. authn/authz and side-effect boundary are defined;
4. state, idempotency, retry, timeout, and DLQ behavior are tested;
5. logs, metrics, traces, and redaction are tested;
6. failure injection and recovery are demonstrated;
7. code, configuration, and evidence are tied to an exact revision;
8. no unresolved critical/high finding blocks its risk tier.

A document row is not a successful wire. Status must be independently determined as `IMPLEMENTED_AND_TESTED`, `IMPLEMENTED_UNVERIFIED`, `PARTIAL`, `SPEC_ONLY`, `DISABLED`, or `BLOCKED`.
