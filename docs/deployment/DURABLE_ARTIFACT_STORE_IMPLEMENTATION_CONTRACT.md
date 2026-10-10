# Durable Artifact Store: Production Implementation Contract

**Status:** proposed implementation contract; not an implemented adapter or deployment approval.  
**Related work:** issue #290; run/review persistence issue #282; unknown-review reconciliation issue #289; security gate issue #275.

## 1. Scope and non-goals

Move authorization packets, work-order governance records, phase outputs, and evidence artifacts away from task-local files as production authority. Keep local filesystem adapters for development and tests only.

This document does not provision AWS, grant IAM permissions, enable public traffic, activate agents, or authorize external business actions.

## 2. Authoritative data model

- **S3 object bytes:** private, encrypted, versioned objects. Store and return the actual S3 VersionId; never treat a mutable object key as an immutable reference.
- **PostgreSQL metadata:** authoritative mapping of logical artifact identity to object version, SHA-256, media type, schema version, provenance, operation ID, actor, and timestamps.
- **Authorization decision state:** remains in the durable command-center ledger. An artifact's existence does not make it current authorization.
- **Evidence lineage:** every run/phase output references exact immutable artifact versions and source revision; preserve predecessor/successor lineage.

Recommended metadata fields: artifact_id, logical_key, object_version_id, sha256, media_type, schema_version, provenance, operation_id, actor_id, created_at. Enforce uniqueness on (logical_key, object_version_id) and on operation_id. Use a separate version/current-pointer record with compare-and-set if a logical key needs a current version; do not overwrite historical records.

## 3. Write protocol and partial failures

1. Validate non-empty metadata, operation ID, actor scope, and content type/schema before upload.
2. Compute SHA-256 over exact bytes.
3. Check whether the operation ID already exists. If it exists with identical digest and metadata, return its existing immutable reference. If any bound value differs, reject with a conflict.
4. Upload bytes to a private versioned S3 key using server-side encryption and least-privilege credentials. Capture the returned version ID.
5. Read back or otherwise verify the exact version and digest according to the configured assurance level.
6. Insert metadata transactionally with a unique operation ID. Only return a committed reference after metadata commit.
7. If the database commit fails after upload, do not return success. Record/recover orphaned object versions through a bounded reconciliation job; never silently make an unreferenced object authoritative.
8. If the outcome of a write is ambiguous, query by operation ID and reconcile. Do not blindly create a second logical write.

S3 and PostgreSQL do not share a transaction. The implementation must document this saga/reconciliation behavior and test failures between each step.

## 4. Read protocol

1. Resolve an artifact reference from authoritative PostgreSQL metadata.
2. Require the caller's actor/tenant scope and requested logical purpose to match policy.
3. Fetch the exact object version, not the latest version by key.
4. Verify SHA-256 and required media type/schema.
5. Reject missing versions, digest mismatch, invalid provenance, stale/expired authorization, or unavailable authoritative metadata. Never fall back to task-local files in production.
6. Log a redacted audit event containing artifact ID, version, digest, actor, decision, and correlation ID; never log secrets or full sensitive payloads by default.

## 5. Current authorization and stale-write safety

- A historical packet remains historical even if its object is readable.
- Current authorization must be resolved from a versioned, authoritative pointer/ledger with explicit expiry and decision status.
- Update current pointers only with a transaction/conditional update against the expected prior version.
- Pending, denied, expired, unknown, or superseded decisions cannot authorize execution.
- A worker must bind its action to the exact authorization version and evidence digest checked before execution.
- Human approval is required for any release or outward action; this storage contract grants no external-action permission.

## 6. Integration points

Replace production authority in:
- src/core/operator_cockpit.py: load_authorization_packets() and load_work_order_governance_records();
- src/webapp/app.py: command-center packet/work-order loading and artifact/evidence references;
- phase/CLI code that reads or writes phase evidence under the checked-out project workspace.

Use dependency injection or a single configured repository factory. Production mode must reject startup or relevant requests if shared storage is unconfigured, unhealthy, non-durable, or cannot establish authoritative state. Do not silently switch to LocalArtifactStore or repository JSON files. Test/development mode may explicitly select local adapters.

## 7. Security and operations

- S3: block public access, enable versioning and encryption, enforce TLS, scope bucket/prefix/version permissions to service roles, and consider Object Lock only where retention requirements justify it.
- PostgreSQL/RDS: private networking, TLS, least-privilege roles, migration discipline, backups/PITR, connection limits, and tested restore procedures.
- Secrets: retrieve runtime credentials from an approved secret manager; never embed keys in images, source, or browser code.
- Observability: metrics for upload/read latency, digest failures, metadata conflicts, orphan versions, denied IAM, store availability, and reconciliation backlog. Redact payloads and secrets.
- Lifecycle: define retention, deletion/legal hold, backup, and data classification policy before production.

## 8. Required tests and acceptance criteria

### Unit tests with fake adapters
- identical operation retry returns the same reference;
- operation ID reused with different bytes or metadata is rejected;
- SHA-256 mismatch, missing object, wrong version, invalid schema, and invalid provenance fail closed;
- local adapter advertises durable=False and is refused in production configuration;
- historical, expired, denied, pending, unknown, and superseded authorization cannot authorize a run.

### Integration tests
- two independent app/worker instances can read the same committed packet and evidence;
- process restart/task replacement preserves artifact lineage and current authorization version;
- concurrent writes to one logical current pointer yield one accepted expected-version transition;
- database outage, S3 outage, denied IAM, timeout/ambiguous upload, and DB commit failure never return false success;
- orphan reconciliation is idempotent and cannot promote orphaned bytes into authorization;
- tampered object versions are rejected on read;
- duplicate requests do not duplicate metadata or repeat business actions.

### Release gate
Require green exact-head CI, independent review, successful integration tests against an S3-compatible test service and PostgreSQL, security review of IAM/network/secret handling, and a human-approved staging receipt. Do not enable public production traffic until the broader issue #275 acceptance suite passes.

## 9. Rollout and migration

1. Inventory existing JSON/filesystem packets and evidence with source path, digest, schema, provenance, and observed authorization status.
2. Import into versioned object storage and PostgreSQL in a non-authoritative dry-run mode; compare digests and record every discrepancy.
3. Require human reconciliation for ambiguous, expired, conflicting, or unverifiable authorization packets.
4. Run dual-read comparison in staging only; never let local data silently override shared authoritative state.
5. Switch production authority only after migration reconciliation, integration tests, restore tests, and explicit approval.
6. Keep rollback reversible: disable new writes safely, preserve immutable artifacts and audit lineage, and do not roll back to unsafe task-local authorization authority.

## 10. Definition of done

- All listed packet/work-order/phase evidence paths use the configured shared store.
- Production refuses to run without healthy authoritative shared storage.
- Exact object versions, digests, provenance, idempotency, and lineage are enforced.
- Multi-instance, restart, partial-failure, stale-authorization, and tamper tests pass.
- Security and independent code review are complete.
- Staging evidence is bound to source SHA, image digest, infrastructure revision, test results, and human approval.

Passing this contract's tests is a prerequisite for cloud deployment, not proof that deployment has occurred.
