# Governed Orchestration Kernel v1

Status: IMPLEMENTATION SLICE — NOT A PRODUCTION CERTIFICATION

## Scope

This increment adds versioned Pydantic contracts, a non-executing Python AST policy auditor, and a Redis Streams coordination adapter. It is deliberately additive to AIGC's existing src/core architecture.

## Epistemic boundary

- **Implemented in this slice:** schema validation; a hard 30-second handler timeout ceiling; task hop-count bounds; atomic Redis idempotency-key reservation plus stream append; consumer-group acknowledgement after result publication; dead-letter routing for invalid tasks and handler failures; a bounded pending-message reclaim entry point; in-process reverse-order Saga compensation.
- **Not proven by these files:** exactly-once execution; crash-safe Saga recovery; PostgreSQL-backed transaction/outbox consistency; Redis failover durability; production latency or throughput targets; a complete operating-system sandbox; independent security review.
- **Assumptions:** Redis is reachable and configured with suitable persistence/replication; handler implementations are idempotent; compensation operations are themselves safe and idempotent.
- **Unknown until measured:** queue latency under target load, upstream provider latency, workload cost, and recovery time after node loss.

## Contract rules

- Messages declare schema_version, stable IDs, idempotency keys, UTC-aware timestamps, telemetry context, and bounded hop counts.
- Task timeout is constrained to (0, 30] seconds. Coordinator configuration cannot raise that ceiling.
- External mutations require references to both a permit and a human approval. These identifiers are not proof by themselves; the execution boundary must verify the referenced evidence.
- Unknown fields are rejected. Contract validity does not imply authorization.

## Redis Streams behavior

- Stream: aigc:tasks:v1
- Consumer group: aigc-workers-v1
- Dead-letter stream: aigc:tasks:dead-letter:v1
- Result stream: aigc:task-results:v1
- Enqueue uses one Redis Lua script to reserve an idempotency key and append the task atomically. The idempotency reservation expires after seven days; tune retention only with an explicit replay policy.
- Delivery is **at least once**. A crash after handler completion but before result publication/acknowledgement can cause handler replay. Handlers must use idempotency keys at every mutation boundary.
- A pending-entry reclaim method is provided, but operators must schedule and monitor it. Consumer crash recovery is not automatic unless that method is called.
- Result events apply key-based and common token-shaped redaction and enforce a 1 MB serialized-result ceiling; redaction is defense in depth, not a guarantee that arbitrary secrets are detected.
- A dead-letter record stores the source message ID, payload digest, and failure class rather than copying the raw task payload. Inspect the original stream entry only under access controls.
- A dead-letter record is appended before acknowledgement. If Redis cannot write the dead-letter record, the original message remains pending.

## Saga semantics and limits

The in-process Saga runner executes bounded steps and compensates attempted steps in reverse order on failure, including the step that raised because it may have partially mutated state. Compensations must be idempotent.

This runner does **not** survive process loss. Do not use it to coordinate irreversible external effects until a durable Saga ledger, transactional outbox, replay-safe state machine, and reconciliation worker are implemented and tested.

## AST arbiter semantics and limits

The arbiter parses source with Python's AST and returns findings without importing or executing the source. Its deny rules are defense in depth, not a proof of safety. AST inspection can be bypassed by obfuscation, native extensions, indirect calls, or interpreter/runtime behavior. Untrusted code must execute only in a separately hardened sandbox with least privilege, no ambient credentials, restricted network, resource quotas, and disposable storage.

## Adversarial acceptance tests

The current focused tests cover:
- timeout and external-mutation contract rejection;
- shell/dynamic execution call detection;
- invalid syntax rejection;
- acceptance of a small pure function;
- reverse-order Saga compensation, including the failed/partially executed step.

Additional required tests before production consideration:
- Redis unavailable during enqueue, result publication, dead-letter write, and acknowledgement;
- duplicate enqueue and duplicate handler delivery;
- consumer crash before and after side effects;
- reclaiming stale pending entries;
- poison messages and maximum-hop boundaries;
- compensation timeout and compensation failure;
- idempotency-key expiry/replay;
- Redis persistence/failover behavior and PostgreSQL transactional outbox recovery;
- load tests that measure queue latency and processing deadlines;
- independent security review of sandbox and authorization evidence verification.

## Deployment status

The Compose stack is a local/staging integration harness. PostgreSQL is wired to the existing command-center durable store. Redis and Qdrant are made available as services, but Qdrant is not integrated into this kernel and the existing web application does not yet instantiate the new Redis coordinator. Do not interpret container health as proof of full application integration or production readiness.

## Operational commands

```bash
# Local/staging only: create .env from the example and use unique credentials.
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs --tail=200 app redis postgres qdrant

# Run repository tests in the app container.
docker compose exec app pytest -q

# PostgreSQL backup.
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > aigc-postgres-backup.sql

# Restore into an explicitly selected, empty staging database.
cat aigc-postgres-backup.sql | docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"'

# Stop services without deleting named volumes.
docker compose down

# Destructive: removes all named data volumes. Use only for disposable local environments.
docker compose down --volumes
```

Before any production deployment, require a reviewed secret-management design, TLS/network policy, authenticated Redis, Qdrant access control, backup restore drills, database migration strategy, alerting, incident response, multi-replica authorization tests, exact-head CI, independent security review, and authorized human release acceptance.

## Architecture decision matrix

Scores are engineering judgments for this repository's current governance requirements, not measured benchmarks. Scale: 1 = weak, 5 = strong.

| Criterion | A. Central orchestrator | B. Pure event choreography | C. Hybrid Saga + directed graph |
|---|---:|---:|---:|
| Throughput / horizontal scale | 3 | 5 | 4 |
| Consistency / invariant enforcement | 5 | 2 | 4 |
| Rollback / compensation traceability | 4 | 1 | 4 |
| Observability / causal reconstruction | 5 | 2 | 5 |
| Operational simplicity | 3 | 2 | 2 |
| Fit for AIGC | 3 | 2 | **5 (recommended target)** |

### Decision

Adopt **C: hybrid Saga-driven directed graph** as the target. Use a durable coordinator for task contracts, budgets, approvals, state transitions, and Saga state; use Redis Streams for bounded asynchronous work distribution; use transactional persistence/outbox semantics for authoritative state changes; use local worker handlers for execution and compensation.

This is a target architecture, not a claim that the current code already implements a durable distributed Saga. The current Redis adapter is a first slice; the in-process Saga runner must not coordinate irreversible external effects until its state and compensation progress are persisted and reconciled.

### Failure-mode and effects analysis (FMEA)

| Failure mode | Impact | Current control | Required next control |
|---|---|---|---|
| Poison message / repeated hop | Queue churn and worker starvation | Schema validation, hop ceiling, dead-letter stream | Monitor DLQ age/count, replay approval, bounded redrive policy |
| Partial multi-step mutation | Cross-system state divergence | Reverse-order best-effort compensation in process | Durable Saga ledger, idempotent compensations, reconciliation worker |
| Malicious actuation source | Unauthorized code execution | AST deny rules only; source is not executed by the arbiter | Disposable OS/container sandbox, syscall/network policy, no ambient secrets |
| Recursive token/cost exhaustion | Budget depletion and cascading retries | Per-task timeout and hop ceiling | Persistent budget ledger, token/cost caps, sliding-window circuit breaker |
| Worker crash after side effect | Duplicate mutation on replay | At-least-once delivery explicitly documented | Mutation idempotency at target, durable execution receipt, pending-entry recovery |
| Redis unavailable during result/DLQ write | Pending work / delayed completion | Acknowledge only after successful result/DLQ write | Alerts, persistence/failover tests, operator recovery runbook |

Latency targets such as sub-500 ms queue delay are acceptance objectives only; they are not established until load tests measure p50/p95/p99 under a declared workload and infrastructure profile.
