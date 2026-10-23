-- PostgreSQL-owned task lifecycle and transactional outbox.
-- Apply only through the reviewed migration process; never run implicitly at app startup.
CREATE TABLE IF NOT EXISTS aigc_tasks (
    task_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 256),
    idempotency_key_sha256 CHAR(64) NOT NULL CHECK (idempotency_key_sha256 ~ '^[a-f0-9]{64}$'),
    request_sha256 CHAR(64) NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    contract_json JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','unknown')),
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    result_json JSONB,
    artifact_bytes BYTEA,
    artifact_sha256 CHAR(64) CHECK (artifact_sha256 IS NULL OR artifact_sha256 ~ '^[a-f0-9]{64}$'),
    evidence_json JSONB,
    failure_class TEXT,
    lease_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT aigc_tasks_owner_idempotency_unique UNIQUE (owner_id, idempotency_key_sha256),
    CONSTRAINT aigc_tasks_terminal_evidence CHECK (
      status <> 'succeeded'
      OR (result_json IS NOT NULL AND artifact_bytes IS NOT NULL
          AND artifact_sha256 IS NOT NULL AND evidence_json IS NOT NULL)
    ),
    CONSTRAINT aigc_tasks_artifact_pair CHECK (
      (artifact_bytes IS NULL AND artifact_sha256 IS NULL)
      OR (artifact_bytes IS NOT NULL AND artifact_sha256 IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS aigc_tasks_owner_updated_idx ON aigc_tasks (owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS aigc_tasks_recovery_idx ON aigc_tasks (status, lease_until);

CREATE TABLE IF NOT EXISTS aigc_task_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE REFERENCES aigc_tasks(task_id) ON DELETE RESTRICT,
    payload_json JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','publishing','dispatched')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    dispatcher_id TEXT,
    lease_until TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT aigc_task_outbox_lease_consistent CHECK (
      (status = 'publishing' AND dispatcher_id IS NOT NULL AND lease_until IS NOT NULL)
      OR (status <> 'publishing' AND dispatcher_id IS NULL AND lease_until IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS aigc_task_outbox_pending_idx
  ON aigc_task_outbox (outbox_id) WHERE status IN ('pending','publishing');
