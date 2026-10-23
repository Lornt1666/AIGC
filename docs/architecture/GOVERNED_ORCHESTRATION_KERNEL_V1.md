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
