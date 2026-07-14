# Production Persistence Baseline v1

Status: `IMPLEMENTED_INTERNAL_PENDING_STAGING_EVIDENCE`  
Parent program: issue `#83`  
Workstream: issue `#87`  
Cloud SQL resource created: **No**  
Secret accessed: **No**  
Data migrated: **No**  
External action performed: **No**

## Purpose

This baseline defines the managed PostgreSQL substrate that must preserve the existing AIGC SQLite domain semantics in staging and production.

SQLite remains the bounded local/offline store. PostgreSQL is the selected managed production engine, but this change does not connect to a database or claim that Cloud SQL exists.

## Canonical artifacts

```text
config/production_persistence_baseline.json
schemas/production_persistence_baseline.schema.json
schemas/database_recovery_receipt.schema.json
migrations/postgresql/0001_transactional_storage.sql
migrations/postgresql/0002_identity_boundary_v1.sql
migrations/postgresql/0003_review_evidence_packet_v1.sql
src/infrastructure/persistence/postgresql/runtime.py
src/infrastructure/persistence/postgresql/migrations.py
```

## Accepted architecture

- Cloud SQL for PostgreSQL;
- Toronto primary region;
- Montréal recovery region;
- Google Secret Manager reference for runtime connection material;
- raw DSN prohibited from source control and runtime summaries;
- Psycopg 3 and `psycopg_pool`;
- bounded connection pool;
- `READ COMMITTED` for ordinary work;
- `SERIALIZABLE` for governed lifecycle transitions and migrations;
- statement and lock timeouts;
- bounded retries for serialization, deadlock, and selected connectivity failures;
- forward-only, checksum-bound migrations;
- transaction-scoped PostgreSQL advisory migration lock;
- JSONB document payloads;
- timezone-aware timestamps;
- database-level append-only triggers;
- RPO 15 minutes and RTO 4 hours.

## Secret boundary

The configured connection reference is intentionally unresolved:

```text
gcp_secret://TBD_PROJECT/aigc-postgres-dsn
```

`PostgresConnectionFactory.open()` rejects this reference before invoking a resolver or creating a pool.

A later staging change must replace only the resource reference after the staging project and access policy are approved. The repository must never contain the resolved DSN or database credential.

## Connection and transaction behavior

The factory is lazy. Importing the application cannot open a database connection.

Opening the pool requires:

1. a non-placeholder Secret Manager reference;
2. an injected resolver authorized for the exact staging workload identity;
3. non-empty resolved connection material;
4. successful pool initialization.

Every transaction applies:

- a reviewed isolation level;
- a transaction-local statement timeout;
- a transaction-local lock timeout.

Governed Quest, identity, authorization, review, and release mutations must use `SERIALIZABLE` transactions once their PostgreSQL repository adapters exist.

Retry behavior is limited to configured PostgreSQL SQLSTATE classes. Unknown application, contract, and integrity errors are not retried.

## Migration behavior

Migration files must:

- use the `NNNN_name.sql` naming convention;
- be non-empty;
- avoid `DROP TABLE`, `TRUNCATE`, and column/table-drop statements;
- possess a SHA-256 checksum;
- execute one migration per transaction;
- acquire a transaction-scoped advisory lock;
- record the version, application timestamp, and checksum;
- reject any checksum mismatch;
- replay idempotently when the checksum is unchanged.

The three PostgreSQL migrations preserve:

```text
records
idempotency_records
authorization_receipts
audit_events
identity_evidence_receipts
review_evidence_packets
review_judgment_receipts
```

Append-only triggers protect:

```text
authorization_receipts
audit_events
identity_evidence_receipts
review_evidence_packets
review_judgment_receipts
```

## Compatibility boundary

This baseline implements:

- connection and pool contract;
- transaction and retry contract;
- migration plan and runner;
- PostgreSQL schema parity;
- future recovery receipt contract.

It does **not** yet implement all PostgreSQL repositories corresponding to the existing SQLite repository classes. Until those adapters exist and pass parity tests, the application composition root must continue to use SQLite.

No dual-write mode is authorized. Migration from SQLite to PostgreSQL requires a separate, deterministic export/import and reconciliation design.

## Tenant and project isolation

Application-level PIBC and authorization bindings already require tenant and project identifiers. Production persistence additionally requires database-enforced isolation.

The current status is:

```text
ADAPTER_AND_STAGING_EVIDENCE_REQUIRED
```

Before completion, PostgreSQL repository operations must set trusted transaction-local tenant/project context and enforce row-level policies or an equivalently reviewed isolation control. Cross-tenant and cross-project negative tests are mandatory.

## Backup and recovery evidence

The future `database_recovery_receipt` contract requires an isolated staging restore bound to:

- exact Git revision;
- immutable backup reference and SHA-256 digest;
- restore target reference;
- measured RPO and RTO;
- schema migration verification;
- record-count reconciliation;
- foreign-key checks;
- receipt digest checks;
- audit-chain verification;
- tenant/project isolation check;
- application health check;
- confirmation that production data was not used.

A passing receipt requires:

```text
measured_rpo_minutes <= 15
measured_rto_minutes <= 240
audit_chain_preserved = true
append_only_receipts_preserved = true
tenant_isolation_negative_passed = true
```

No passing recovery receipt exists yet.

## Required staging sequence

After issue #85 supplies approved project and billing identifiers and a separate resource-creation authority is granted:

1. create an isolated staging project and workload identity;
2. provision Cloud SQL PostgreSQL with private connectivity;
3. create a Secret Manager resource and grant only the staging workload identity access;
4. update the staging secret reference outside source-controlled secret values;
5. open the pool and run migration `0001` through `0003`;
6. rerun migrations to prove checksum-bound idempotency;
7. exercise concurrent lifecycle transitions and retry behavior;
8. implement and test database row isolation;
9. create an encrypted staging backup;
10. restore into a separate isolated instance;
11. validate receipts, audit chain, records, constraints, and health;
12. measure RPO/RTO and emit a recovery receipt;
13. perform accountable-operator review.

## Rollback

The migration strategy is forward-only. Rollback of application code means deploying a prior compatible application artifact, not deleting migration history.

If a migration fails:

- its transaction rolls back;
- its ledger row is not written;
- the deployment remains blocked;
- the failure is recorded without connection material;
- correction occurs through a new forward migration.

For a release rollback after a successful schema change:

- verify the prior application remains schema-compatible;
- otherwise restore the prior database into an isolated environment and follow the disaster-recovery procedure;
- never mutate append-only receipts to simulate rollback.

## Current blockers

The evaluator intentionally reports `production_complete: false` because the following remain absent:

```text
Cloud SQL instance observation
migration-lock staging observation
prior-schema upgrade test
concurrent transition staging test
connection-loss retry staging test
backup integrity receipt
isolated restore receipt
measured RPO
measured RTO
cross-tenant negative evidence
detailed backup schedule
database row isolation
complete PostgreSQL repository adapters
```

## Readiness truth

This slice may justify stronger structural evidence for `transactional_persistence`, but it does not justify `complete` or removal from `blocking_gaps`.

The readiness ledger remains unchanged. An evidence-only promotion PR is permitted only after issue #87 exit criteria are satisfied at one exact revision.
