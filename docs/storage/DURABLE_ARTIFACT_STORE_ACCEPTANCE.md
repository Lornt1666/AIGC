# Durable artifact store — implementation and acceptance packet

Status: implementation candidate on a feature branch; not production approved. No cloud resources are provisioned by this change.

## Authority model
- PostgreSQL metadata is authoritative for whether an artifact reference exists and which exact S3 VersionId it names.
- Private S3 stores bytes in a bucket with versioning enabled. Reads always specify the exact VersionId and verify SHA-256.
- A successful S3 upload without a committed PostgreSQL metadata row is an orphan, not an authorized artifact. Reconciliation must report/delete orphans only under a separately reviewed retention policy.
- Authorization must bind to the exact artifact reference and current approval/version. A durable packet is not automatically a current approval.
- Production must fail closed if PostgreSQL metadata cannot be read/committed, S3 access is denied/unavailable, an object has no real VersionId, or the digest/reference mismatches.

## Current code in this slice
- `src/core/production_artifact_store.py`: S3 + PostgreSQL adapter, idempotency by operation ID, advisory transaction lock per logical key, expected-current-version compare, exact-version read, SHA-256 verification, fail-closed exceptions.
- `migrations/artifact_store/0001_artifact_metadata.sql`: authoritative metadata table and indexes.
- `tests/test_production_artifact_store.py`: fake-client unit tests for round trip, idempotency, conflicting operation IDs, stale writes, denied/unavailable S3, unversioned responses, and digest tampering.

## Important limitations before merge
- The adapter is not yet wired into `operator_cockpit.py`, web review endpoints, phase 5/6/7, or pipeline closure. Do not treat the PR as closing issue #290.
- This code uses the existing psycopg pool contract and a caller-supplied S3 client; production bootstrap, IAM policy, bucket policy, KMS policy, region, retention/object-lock decisions, health checks, and SDK dependency locking remain to be completed and reviewed.
- Fake tests do not establish AWS IAM, S3 versioning, PostgreSQL concurrency, transaction failure, or multi-instance guarantees. Add integration tests against isolated private staging services before acceptance.
- Verify all SQL row shapes and transaction behavior against the actual psycopg 3 pool/version in CI. Any exception must block authorization; do not fall back to local files in production.
- A failed metadata transaction after S3 upload can leave an orphaned S3 version. Do not automatically retry with a new operation ID; retain the operation ID and reconcile the uncertain result first.

## Independent review packet
Reviewer must be independent of the author and assess:
1. SQL transaction and advisory-lock correctness across concurrent workers and isolation levels.
2. Idempotency conflict behavior and expected-current-version semantics, including an existing logical key when expected version is omitted.
3. S3 versioning, exact VersionId retrieval, encryption, private bucket policy, least-privilege IAM, and KMS access-denied behavior.
4. Orphan handling after S3 success / PostgreSQL rollback and safe reconciliation without granting authority.
5. Integrity verification, metadata/reference equality, provenance completeness, and no local-file fallback.
6. Integration coverage for cockpit, work orders, phase evidence, and approval freshness.
7. CI, migration rollback/forward strategy, operational observability, secret redaction, dependency pinning, and recovery drill.

## Private staging acceptance criteria
- Use an isolated, non-production account/project and private network boundary; no public ingress.
- Confirm S3 Block Public Access, bucket versioning, encryption at rest, TLS, least-privilege service role, and denied public principal.
- Apply migration twice safely; validate forward migration and documented recovery.
- Two independent app instances can write/read the same artifact and see the same authoritative metadata.
- Restart/replace a worker and read the exact committed version with the same digest.
- Concurrent same-key writers with a stale expected version: exactly one accepted; stale writer receives conflict and cannot overwrite authority.
- Identical operation retry returns the same reference; operation-ID reuse with different bytes/metadata is rejected.
- Missing object, wrong digest, invalid/missing VersionId, S3 AccessDenied/timeout, PostgreSQL outage/rollback, and orphaned object all fail closed.
- A previously approved packet becomes unusable when the authoritative version/approval binding changes; no implicit re-approval.
- CI and integration evidence are tied to the exact candidate commit SHA; independent review and human release approval are recorded.
- Deployment remains blocked until #275 authentication/security acceptance and #282/#289 durable run/review recovery/reconciliation gates are satisfied.

## PR #292 reconciliation
1. Keep #292 draft; do not force-update its branch via contents API.
2. Rebase its existing head onto current main in a Git-capable checkout, preserving both local-adapter files and checking for conflicts.
3. Run canonical CI on the resulting exact head; record head SHA and all required jobs.
4. Obtain independent review of the contract and local adapter; do not use author comments or green CI as review.
5. Keep this production implementation candidate as a separate draft until it can be cleanly rebased atop the reviewed contract and its integration tests pass.
6. Merge neither PR without independent review and repository policy gates. PR #297 is explicitly excluded from merge actions.
