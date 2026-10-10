# AIGC Command Center durable-state operations

Status: implementation/runbook only. This document does not provision AWS, apply a database migration, authorize a production action, or claim a live deployment.

## Required configuration

- AIGC_ENV=production
- AIGC_COMMAND_CENTER_DATABASE_URL supplied from AWS Secrets Manager through the approved ECS task definition. Never commit a DSN/password or print it to logs.
- AIGC_COMMAND_CENTER_DB_SSLMODE=verify-full (default). Do not disable TLS in production.
- Apply migrations 0001_durable_command_center.sql and 0002_emergency_stop_and_audit.sql in lexical order using an approved migration runner from an authorized network location.
- GET /readyz must report durable_state=true and backend=postgresql. It must return 503 if the DSN or required schema is missing.

The memory adapter is development/test-only and reports durable=false. Production mode refuses to fall back to process-local state.

## Emergency stop

1. An authenticated operator calls POST /api/emergency-stop. The PostgreSQL control row is committed first, increments the stop epoch on the inactive-to-active transition, and appends an immutable control event. The local AIGC CLI stop command is then invoked as a secondary safeguard.
2. GET /api/emergency-stop shows the current active flag and epoch.
3. New runs are rejected while the stop is active. Existing runs cannot begin another phase after the stop or a stop-epoch change. A subprocess already in progress is bounded by the configured timeout; the stop does not claim to retroactively undo a command already running.
4. To clear, review the current stop state, then call POST /api/emergency-stop/clear with expected_epoch, a reason of 10–2000 characters, and the exact phrase: CLEAR AIGC EMERGENCY STOP EPOCH <epoch>. The local CLI clear must succeed before the database flag is cleared. The clear is idempotent for the same inactive epoch.
5. Every activation and clear is written to command_center_control_events. Updates and deletes are rejected by database triggers. The runtime database role must not have schema-owner, trigger-disable, or table-owner privileges.

## Unknown run reconciliation

A worker or database failure can leave a run in status unknown. Unknown is a deliberate safety state: it continues to block new run admission, and the worker never retries the run automatically.

1. Inspect the durable run receipt, recorded steps/evidence, relevant local CLI state, and external-side-effect boundaries.
2. Only after an operator confirms the cycle must not be retried, submit POST /api/run/<run_id>/reconcile with the current expected_version and exact phrase: RECONCILE AIGC RUN <run_id> AS FAILED VERSION <version>.
3. The API is authenticated. A successful reconciliation atomically transitions the unknown run to failed and appends an immutable receipt to command_center_run_reconciliations. The receipt stores the operator identity fingerprint and a hash of the confirmation phrase, not the phrase itself.
4. If the version changed, reload the run and reassess. Do not force-update rows or delete audit evidence.

## Validation before production

- Run the PostgreSQL integration tests against an isolated test database; verify cross-instance state, one-run admission, restart recovery, concurrent review claims, stop propagation, exact-phrase clearing, append-only audit, and transaction rollback.
- Verify backups and restore in staging, connection limits, TLS verification, database least privilege, CloudWatch redaction/retention, and cost alerts.
- Ensure browser identity/session authentication is accepted end-to-end (issue #275).
- Ensure authorization packets, work orders, and their source evidence are shared and durable; these remain file-backed today.
- Do not declare deployment ready until a real private RDS staging receipt, protected-route tests, image digest, and live authenticated health check are recorded.
