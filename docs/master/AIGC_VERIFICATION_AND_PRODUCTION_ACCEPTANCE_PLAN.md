# AIGC Verification and Production Acceptance Plan

**Version:** 1.0.0-draft  
**Status:** Required test plan; not evidence that tests have passed.  
**Release posture:** BLOCKED until all applicable gates are independently evidenced.

## 1. Verification principles

- Test observable behavior, not intention or documentation alone.
- Bind test evidence to the exact commit, configuration, dependencies, image digest, and policy version.
- Include positive, negative, boundary, concurrency, fault-injection, recovery, and adversarial cases.
- Distinguish test failure from unavailable test, skipped test, flaky test, and not-yet-implemented behavior.
- Do not use a successful unit test to claim integration, security, load, or disaster recovery success.
- Never accept a producer's `passed=true` field without verifying source and evidence.

## 2. Test layers

### L0 — static and repository checks
- syntax, import graph, lint/type checks where configured;
- secret scanning;
- dependency lock consistency and vulnerability scanning;
- container/Compose/Terraform manifest validation;
- workflow action SHA pinning and image digest checks;
- schema and migration consistency.

### L1 — unit tests
- contract bounds, enum/state transition rules, canonical serialization and digesting;
- idempotency key conflict behavior;
- retry/deadline/budget calculations;
- AST arbiter limits and documented detections;
- permit decision logic and receipt verification;
- artifact manifest/archive validation;
- redaction and data classification.

### L2 — component integration
- ingress → contract validator → registry → state store;
- state/outbox transaction → publisher → Redis Streams;
- consumer → worker → durable result → acknowledgement;
- secret broker → fake provider and policy decisions;
- phase registry → CLI command and schema;
- memory metadata → retrieval filter;
- telemetry propagation through API/coordinator/worker/adapter.

### L3 — end-to-end staging
- synthetic pipeline across approved phases;
- read-only public data replay;
- approval packet created, denied, revised, expired, and approved in tests;
- approved action remains limited to exact payload/target/scope;
- no action occurs from pending, denied, expired, or modified packet;
- emergency stop blocks new effects;
- closure packet bound to exact SHA and digest.

### L4 — security/adversarial
- prompt injection in documents, feed content, tool output, and memory;
- spoofed producer identity, forged permit, wrong audience, wrong action/resource, revoked/expired permit;
- replay and concurrent duplicate receipt claims;
- malicious or oversized payloads, deep nesting, invalid UTF-8/surrogates, archive traversal, symlinks, unexpected files;
- SSRF/egress attempts, path traversal, shell injection, dynamic imports and execution;
- secret leakage into logs, prompts, artifacts, exception text, and telemetry;
- privilege escalation, confused deputy, agent self-approval, and disabled-agent dispatch;
- artifact digest tampering, wrong signer, wrong workflow, wrong candidate SHA;
- evidence pagination omission and stale CI attempt.

### L5 — reliability and chaos
- crash after DB commit but before publish;
- publish success followed by crash before local acknowledgement;
- duplicate message delivered to two workers;
- worker crash before and after external effect;
- Redis outage, reconnect, pending reclaim, and stream retention/trimming;
- PostgreSQL failover or connection interruption;
- provider timeout, rate limiting, malformed response, and circuit breaker;
- DLQ poison message and controlled replay;
- Saga compensation failure and external outcome ambiguity;
- emergency stop during queued, running, and reconciling states.

### L6 — performance
- define workload, concurrency, payload sizes, provider, hardware, and duration;
- measure p50/p95/p99 latency, queue wait, throughput, error rate, memory/CPU, DB connections, queue growth, and provider cost;
- validate queue latency target (<500 ms) only against a declared load profile;
- validate default per-agent timeout (30 s) and hop cap (10) using boundary tests;
- prove load shedding and budget enforcement before resource exhaustion;
- record variance, sample size, and bottlenecks.

### L7 — recovery and operations
- restore backup into isolated environment;
- reconcile schema migrations, tasks, outbox, idempotency claims, and audit ledger;
- test RPO/RTO against explicitly approved targets;
- test alert delivery and escalation;
- execute runbook during a timed drill;
- verify rollback to a prior immutable artifact and schema-compatible state.

## 3. Mandatory negative tests

| Test | Stimulus | Required result |
|---|---|---|
| T-001 | Unknown agent/phase ID | Reject; no dynamic import or dispatch |
| T-002 | Disabled/spec-only agent | Reject scheduling |
| T-003 | Payload exceeds byte or nesting limit | Deterministic reject before expensive work |
| T-004 | Unknown major schema version | Reject and record reason |
| T-005 | Hop count exceeds limit | Stop chain; no child work |
| T-006 | Deadline or permit expired | Block new protected effect |
| T-007 | Policy source unavailable | Fail closed for protected actions |
| T-008 | Same idempotency key, same digest | Return prior state/result or safely resume |
| T-009 | Same idempotency key, different digest | Conflict; no effect |
| T-010 | Concurrent duplicate claims | One logical effect at most |
| T-011 | Worker crashes after effect, before ACK | Redelivery reconciles; no duplicate effect |
| T-012 | Newer CI attempt fails after older pass | Closure blocked |
| T-013 | Conflicting records for same CI attempt | Closure blocked |
| T-014 | Artifact digest or subject mismatch | Reject artifact |
| T-015 | Provenance signer/builder not trusted | Reject provenance |
| T-016 | Candidate SHA changes during closure | Discard digest and restart |
| T-017 | Human approval binds old payload | Reject changed payload |
| T-018 | Prompt injection asks agent to disclose secret | No secret retrieval/disclosure |
| T-019 | Secret-like value appears in log output | Redaction test fails build |
| T-020 | DLQ message replayed without approval | Reject replay |
| T-021 | Restore omits an outbox or receipt claim | Recovery gate fails |
| T-022 | Telemetry source is stale/unavailable | Show unknown/degraded, never green |
| T-023 | Emergency stop is active | No new protected effect |
| T-024 | Static AST passes but execution permit absent | No code execution |
| T-025 | Unknown external outcome | RECONCILING/NEEDS_OPERATOR, not blind retry |
| T-026 | Disabled external adapter | Request fails closed without network access |

## 4. Fault injection matrix

For each injected fault, record:
- exact SHA/config;
- precondition and injection point;
- task/message/operation IDs;
- expected state;
- observed state;
- side-effect count;
- durable record count;
- recovery time;
- logs/trace/metrics;
- pass/fail and reviewer.

Required crash points:
1. before database transaction;
2. after state write but before transaction commit;
3. after commit before outbox publish;
4. after publish before publisher checkpoint;
5. after message delivery before worker start;
6. after idempotency claim;
7. before external effect;
8. during external effect;
9. after external effect before receipt commit;
10. after receipt commit before Redis ACK;
11. during compensation;
12. during candidate evidence acquisition;
13. after candidate readback but before final decision;
14. during backup restore/reconciliation.

A test passes only if the final state is explainable, no unauthorized or duplicate effect occurred, durable evidence is consistent, and operator escalation is explicit when reconciliation cannot decide safely.

## 5. Evidence acceptance model

Each evidence item must capture:
- source system and authenticated identity;
- observation timestamp and retrieval method;
- raw source reference or retained raw bytes where permitted;
- content digest;
- candidate SHA/config/policy version;
- run ID and attempt if CI-related;
- artifact subject and digest if artifact-related;
- verifier identity and version;
- result and structured failure reason;
- completeness/pagination status;
- expiry/revocation state where relevant.

Evidence lifecycle:
1. **Observed** — read from named source.
2. **Integrity checked** — bytes/digest match.
3. **Authenticated** — source/issuer identity is trusted.
4. **Authorized** — source and action are within policy.
5. **Candidate bound** — exact SHA/run/attempt/subject match.
6. **Fresh and complete** — latest attempts/pages captured; candidate re-read.
7. **Independently evaluated** — acceptance policy checks evidence rather than trusting producer claims.

## 6. Production closure gates

| Gate | Requirement | Pass evidence | Block conditions |
|---|---|---|---|
| G0 Candidate | Live PR/head/base and final re-read | Timestamped source response and SHA match | Changed or unavailable head/base |
| G1 CI | All required jobs pass on exact head and latest attempts | Workflow/run/attempt/job/log records | Missing, queued, failed, stale, conflicting job |
| G2 Artifact | Bytes, manifest, digest, subject and safe archive validated | Verification output and hashes | Mismatch, missing manifest, unsafe path |
| G3 Repository protection | Effective rulesets/protection verified | Authorized readback | Inaccessible or missing required protection |
| G4 Independent security review | Qualified reviewer; findings closed and retested | Reviewer identity, exact SHA, finding evidence | No reviewer, self-review, unresolved blocking finding |
| G5 Supply chain | Lockfile, SBOM, vulnerability policy, trusted provenance | Digests, scan output, verified attestation | Mutable/untrusted build input or unverifiable provenance |
| G6 Runtime security | Permits, isolation, secret boundaries, egress controls | Negative tests and config evidence | Arbitrary execution, missing permit enforcement, secret leak |
| G7 Reliability | Outbox, idempotency, queue recovery, Saga tests | Fault-injection report | Duplicate/lost effect, unbounded retries, ambiguous state ignored |
| G8 Operations | Telemetry, alerts, backup restore, RPO/RTO | Drill and dashboard/alert evidence | Untested restore or silent critical failure |
| G9 Human acceptance | Authenticated acceptance tied to candidate/digest | Signed or otherwise authenticated receipt | Stale or ambiguous approval |
| G10 RX-19 decision | Final authorized decision for same candidate/digest | Authenticated decision receipt | Missing, invalid, or mismatched receipt |

All applicable gates must pass. A gate can be waived only through an explicit, authenticated, policy-compliant risk acceptance by the authorized role; no agent can waive its own blocker. Critical security gates must not be waived merely to release.

## 7. Candidate freshness rules

- Capture all pages of run/review/artifact inventories or mark evidence incomplete.
- Group CI attempts by workflow run ID and evaluate the highest observed attempt.
- A later failed, cancelled, queued, or in-progress attempt invalidates an earlier success.
- Conflicting records for the same attempt block.
- Artifact must correspond to the eligible successful run attempt and expected artifact subject.
- Re-read PR head/base and policy/trust state after verification.
- If anything changes, recalculate all dependent evidence and the canonical digest.
- Never call a run “passed” until the workflow reaches a terminal successful state and every required job is successful.

## 8. Performance and SLO reporting template

Every reported latency/throughput result must include:
- candidate SHA and config digest;
- host/container specs;
- dependency versions;
- test duration and warm-up;
- offered request rate and concurrency;
- payload distribution and workload mix;
- provider and model if applicable;
- p50/p95/p99, throughput, error rate, saturation, and cost;
- sample size and confidence/variance;
- test commands and raw results.

Targets in the prompt (queue latency <500 ms, agent processing timeout <30 s, maximum hops 10) are initial policy candidates. They are not achieved SLOs until measured under a defined workload and approved.

## 9. Required deliverables for each production candidate

- master spec, wiring registry, and runbook reconciled to implementation;
- current component/agent inventory with explicit status;
- schema registry and compatibility policy;
- threat model and FMEA;
- CI results and test logs;
- dependency lock, SBOM, vulnerability report, image digests, provenance verification;
- independent review report and finding closure;
- fault-injection and recovery report;
- telemetry coverage and alert test;
- backup restore report with RPO/RTO;
- effective repository protection evidence;
- human acceptance;
- RX-19 decision receipt;
- canonical evidence digest and post-check candidate SHA.

## 10. References

- NIST AI RMF Generative AI Profile: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- NIST SSDF SP 800-218: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- SLSA provenance: https://slsa.dev/spec/v1.2/provenance
- GitHub artifact attestations: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- Redis Streams: https://redis.io/docs/latest/develop/data-types/stream/
- PostgreSQL backup/restore: https://www.postgresql.org/docs/current/backup.html
- OpenTelemetry signals: https://opentelemetry.io/docs/concepts/signals/
