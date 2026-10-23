# RX-162 — Production Hardening Execution Plan

**Status:** ACTIVE ENGINEERING PLAN — NOT A RELEASE APPROVAL  
**Repository:** `Lornt1666/AIGC`  
**Parent candidate:** PR #334 / RX-148  
**Authority:** RX-19 remains the sole release decision authority  
**Default execution mode:** dry-run; new agents disabled and R0

## 1. Ground truth and epistemic classes

### Observed repository facts

- The RX-148 closure workflow evaluates a nine-gate release matrix and verifies signed Ed25519 receipts against a separately provisioned trust store.
- The RX-148 live runner is read-only and does not merge, deploy, assign reviewers, mutate protection, or release.
- The closure runner does not yet download GitHub artifact ZIP bytes and independently recompute archive/file digests. The artifact-integrity gate must remain BLOCK/UNVERIFIABLE until that implementation is tested.
- `docker-compose.yml` declares an app, PostgreSQL, Redis, and optional Qdrant. App is attached to internal `backend` and `runtime` networks; PostgreSQL is on `backend`, Redis and Qdrant on `runtime`. Redis/PostgreSQL ports are not published to the host.
- The app defaults to `AIGC_DRY_RUN=true`, drops Linux capabilities, uses a read-only root filesystem and runs as an unprivileged UID.
- The current Dockerfile uses mutable `python:3.12-slim-bookworm` tags and installs range-based `requirements.txt` entries without a hash-locked dependency file. These are known supply-chain reproducibility gaps.
- Compose uses `sslmode=disable` for its internal PostgreSQL connection. This is acceptable only for the isolated local Compose topology; it is not an approved setting for remote or production database endpoints.
- The latest observed PR #334 head was `ea707e1d86191172003095ec0616c9140e3b5fc8`. A subsequent commit invalidates any exact-head CI claim; always re-read the live PR head before interpreting results.

### Design assumptions (must be tested)

- Processes and hosts fail; requests and messages can be duplicated, delayed, reordered, or delivered after a timeout.
- LLM completions and external provider latencies are nondeterministic. A 30-second timeout is a policy ceiling, not a guarantee that a provider stopped work at that instant.
- Exactly-once effects cannot be assumed across arbitrary external systems. Use idempotency, durable intent, reconciliation and compensating actions; document effects that cannot be compensated.
- AST inspection is a static risk filter, not a security sandbox. It cannot prove arbitrary Python is safe.

### Explicit unknowns

- Effective branch protection and required checks for both the candidate base and release branch, until authenticated administrator evidence is recorded.
- Independent security reviewer identity, independence, review findings and retests.
- Verified artifact bytes, trusted builder provenance and retention/retrieval test.
- Production database topology, TLS/certificate management, backup RPO/RTO and successful restore-drill evidence.
- Measured queue latency, end-to-end processing latency, provider timeout distributions, token/cost ceilings and concurrency limits under load.

## 2. Architecture decision

Use a **hybrid Saga-driven directed graph**:

1. PostgreSQL is the authoritative ACID state ledger for task state, idempotency records, saga steps, mutation intent, permit use and audit references.
2. Redis Streams is the transport and scheduling layer, not the source of truth.
3. A transactional outbox commits domain state and outgoing event intent in one PostgreSQL transaction. A relay publishes events; consumers acknowledge only after durable processing.
4. Consumers use a unique idempotency key scoped to tenant/task/step/action. Duplicate delivery returns the recorded outcome instead of repeating a mutation.
5. Saga steps define forward action, deadline, retry classification, reconciliation query, compensation action, and compensation outcome. Compensation is a new action, not a claim that a distributed transaction was rolled back atomically.
6. L1 memory is ephemeral and task-scoped; L2 vector retrieval is optional, tenant-authorized, and non-authoritative; L3 PostgreSQL holds canonical state and evidence references.
7. All agent messages carry schema version, correlation/trace ID, task ID, sender/recipient IDs, policy version, idempotency key, deadline, hop count, payload digest and authorization context. Reject unknown schema versions and hop counts greater than 10.
8. Execution adapters run out-of-process with least-privilege identities, read-only filesystem where possible, no ambient credentials, explicit egress policy, resource limits and per-tool capability permits. AST validation remains defense in depth.

## 3. Architecture trade-off matrix

Scores are relative (1 = weak, 5 = strong) for this project's governance needs; they are design judgments, not benchmark results.

| Criterion | Centralized orchestrator | Pure event choreography | Hybrid Saga graph |
|---|---:|---:|---:|
| Throughput/scaling | 3 | 5 | 4 |
| Consistency and state ownership | 4 | 2 | 5 |
| Rollback/compensation clarity | 4 | 1 | 4 |
| End-to-end observability | 4 | 2 | 5 |
| Operational simplicity | 4 | 2 | 2 |
| Overall fit for governed mutation | 3 | 2 | **5** |

The hybrid option has higher operational overhead than a single controller, but explicit state ownership, durable workflow history and auditable compensation are more valuable than minimizing component count for a system capable of external mutations.

## 4. Required runtime bounds

Treat the following as initial policy values to verify through load and failure tests, not measured guarantees:

- Queue-latency objective: p95 below 500 ms under a documented workload and healthy dependencies.
- Per-agent execution deadline: 30 seconds maximum for synchronous steps; long-running jobs must use persisted asynchronous state rather than extending the request indefinitely.
- Maximum hop count: 10; reject and dead-letter above the limit.
- Concurrency: configured per agent, per tenant, and globally; enforce at the scheduler and downstream provider where possible.
- Retry: exponential backoff with full jitter, `delay = random(0, min(cap, base * 2^attempt))`; retry only transient, idempotent or reconciled actions.
- Budgets: hard limits for wall time, input/output tokens, tool calls, provider spend and recursion depth. Budget exhaustion terminates or moves the job to human review.
- Circuit breakers: bounded sliding window, explicit open/half-open/closed states, provider-specific thresholds and observable transitions.
- Poison messages: bounded delivery count, redacted failure reason, dead-letter queue, operator replay requiring authorization and a new replay record.
- Telemetry: propagate W3C trace context; structured logs must redact credentials, tokens, private prompts and sensitive payloads.

## 5. Adversarial failure-mode register

| Failure mode | Required control | Acceptance evidence |
|---|---|---|
| Poison-pill loop | schema validation, hop cap, delivery cap, DLQ | injected poison payload reaches DLQ within bounded deliveries; no cross-group infinite loop |
| Duplicate mutation | durable idempotency key and uniqueness constraint | concurrent duplicate requests create one external effect or one reconciled outcome |
| Crash after side effect, before ack | reconciliation-before-retry | kill process at each boundary; no blind duplicate action |
| Partial multi-agent mutation | persisted Saga state and step-specific compensation | inject failure at each step; all compensations attempted and residual state reported |
| Prompt injection via tool/retrieval content | treat retrieved text as data, capability allowlist, downstream authorization | red-team suite cannot escalate tool scope or exfiltrate unauthorized data |
| Malicious code in payload | no eval/exec of payload, static AST screening, isolated worker | payload never executes in controller; sandbox escape tests fail closed |
| Token/cost exhaustion | per-task/tenant/provider budgets and circuit breaker | synthetic recursion stops at hard ceilings and emits an auditable reason |
| Permit replay or revocation race | short-lived signed scoped permits, nonce/use ledger, atomic consumption | concurrent replay accepted at most once; revoked/expired/wrong-target permits rejected |
| Artifact substitution | retrieve exact artifact bytes, recompute digest, verify provenance | digest and attestation subject match exact expected commit/workflow/artifact |
| Telemetry outage | bounded local buffering, no secret leakage, fail-safe policy | service remains bounded; security audit events are not silently dropped |

## 6. Required implementation sequence

### P0 — reproducible build and deployment checks

- Pin base images by immutable digest and dependencies through a generated, reviewed lockfile with hashes. Do not fabricate a lockfile manually.
- Add CI checks that run `docker compose config --quiet`, build the image, inspect effective user/capabilities/filesystem/network posture, and assert no host-published Redis/PostgreSQL ports.
- Run an integration smoke test proving the app can reach Redis and PostgreSQL over the intended network and cannot reach arbitrary egress by default.
- For remote database use, require TLS certificate validation and a secret-manager-backed credential; reject `sslmode=disable` outside local isolated Compose.
- Keep Qdrant optional. Never make vector retrieval authoritative for authorization or task state.

### P1 — durable orchestration and failure recovery

- Validate transactional outbox/inbox behavior with concurrent writers and process termination at every commit/publish/ack boundary.
- Verify consumer-group pending-entry recovery, bounded retry, DLQ replay controls and poison-message quarantine.
- Verify Saga compensation contracts are idempotent, observable, and explicit about irreversible external side effects.
- Add database migration versioning, expand/contract migration policy, connection pool limits, lock/statement timeouts and backup/restore drills.
- Establish measured SLOs and load-test results before claiming the 500 ms/30 s targets.

### P2 — security and AI red teaming

- Enforce deny-by-default, short-lived signed permits bound to issuer, agent, task, tool, action, resource, policy version, candidate/contract digest, expiry, nonce and maximum uses.
- Enforce authorization again in each downstream adapter; a model-generated plan is never authority.
- Add adversarial tests for direct/indirect prompt injection, retrieval poisoning, cross-tenant retrieval, tool output injection, data exfiltration, unbounded recursion and unsafe output handling.
- Use an isolated execution worker for any untrusted code or tool payload. AST checks must never be the only control.
- Define privacy-aware retention, redaction, tenant isolation and incident-response procedures.

### P3 — independent release evidence

- Re-fetch PR metadata and CI after the final code commit; all required jobs must pass on the exact head SHA.
- Download actual GitHub artifact bytes, verify archive/file digests, and compare them to a trusted manifest.
- Verify build provenance/attestations against the expected repository, workflow identity, event, commit SHA and subject digest.
- Obtain authenticated effective protection readback for the actual base and release branches.
- Have an authorized administrator assign a qualified independent reviewer; bind findings and retests to the exact reviewed SHA.
- Obtain authenticated human acceptance bound to the final commit and evidence-package digest.
- Submit the complete packet to RX-19. A closure evaluator can report readiness but cannot authorize itself.

## 7. Deployment and recovery commands

Run only in an isolated non-production environment until all gates are closed.

```sh
# 1. Inspect and validate rendered Compose configuration.
docker compose config --quiet
docker compose config

# 2. Build without publishing.
docker compose build --pull

# 3. Start only the local dry-run stack.
docker compose up -d postgres redis app
docker compose ps
docker compose logs --no-color --tail=200 app postgres redis

# 4. Verify health endpoints from the host-bound loopback port.
curl --fail --silent --show-error http://127.0.0.1:${AIGC_HOST_PORT:-8080}/health/live
curl --fail --silent --show-error http://127.0.0.1:${AIGC_HOST_PORT:-8080}/health/ready

# 5. Run the focused tests and compile checks from the project virtual environment.
PYTHONPATH=src python -m pytest -q tests/test_aigc_closure_workflow.py tests/test_aigc_evidence_adapters.py tests/test_aigc_agent_operations.py
python -m compileall -q core src/aigc_runtime scripts

# 6. Capture state for diagnosis without exposing secrets.
docker compose ps
docker compose logs --no-color --tail=500 app > app-diagnostic.log
```

Do not run `docker compose down -v` as a routine recovery command; it destroys named volumes. Do not restore a database backup over a live target without a change-controlled recovery procedure.

### Backup and disaster recovery acceptance

- Define RPO/RTO from business impact before choosing backup frequency.
- Use PostgreSQL-native consistent backups plus WAL archiving/PITR for a real deployment; encrypt backups and keep credentials outside the repo.
- Back up Redis only as needed for transport recovery; reconstruct queue state from the durable PostgreSQL ledger/outbox.
- Back up Qdrant independently if its index is needed; otherwise document deterministic re-embedding/rebuild procedures from authorized source data.
- Test restore into a clean isolated environment, verify row counts and invariants, reconcile in-flight Sagas, and preserve an evidence digest of the drill.
- Recovery is not complete until idempotency/outbox state and external side effects are reconciled.

## 8. Acceptance gate

Production integration remains **BLOCKED** until all P0–P3 requirements have exact, reviewable evidence; the relevant services are implemented and tested in an isolated environment; the independent reviewer signs off; authorized human acceptance is recorded; and RX-19 issues the sole release decision.

## 9. Primary references

- NIST SP 800-218, Secure Software Development Framework (SSDF): https://csrc.nist.gov/pubs/sp/800/218/final
- GitHub Actions secure use: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub artifact attestations and provenance verification: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- OWASP GenAI Security Project, LLM Top 10 (2026): https://genai.owasp.org/llm-top-10/
- OWASP DevSecOps AI/LLM application security testing guidance: https://github.com/OWASP/DevSecOpsGuideline/blob/master/current-version/2-Process/2-4-Test/2-4-6-AI-LLM-Application-Security-Testing.md

These references inform the control plan; they are not evidence that AIGC currently satisfies the controls.
