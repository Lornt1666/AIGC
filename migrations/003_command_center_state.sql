BEGIN;
CREATE TABLE IF NOT EXISTS aigc_schema_migrations (
    version INTEGER PRIMARY KEY,
    migration_name TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS command_center_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    idempotency_key_sha256 CHAR(64) NOT NULL UNIQUE CHECK (idempotency_key_sha256 ~ '^[a-f0-9]{64}$'),
    request_sha256 CHAR(64) NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    status VARCHAR(16) NOT NULL CHECK (status IN ('queued','running','completed','failed','timed_out','unknown')),
    steps JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(steps)='array'),
    current_step TEXT NOT NULL DEFAULT '',
    complete BOOLEAN NOT NULL DEFAULT FALSE,
    admission_slot SMALLINT CHECK (admission_slot IS NULL OR admission_slot BETWEEN 1 AND 64),
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT command_center_terminal_state_consistent
        CHECK (complete = (status IN ('completed','failed','timed_out','unknown')))
);
CREATE UNIQUE INDEX IF NOT EXISTS command_center_runs_active_slot_uq
    ON command_center_runs (admission_slot)
    WHERE status IN ('queued','running') AND admission_slot IS NOT NULL;
CREATE INDEX IF NOT EXISTS command_center_runs_status_lease_idx
    ON command_center_runs (status,lease_expires_at);

CREATE TABLE IF NOT EXISTS command_center_review_decisions (
    action_id VARCHAR(200) PRIMARY KEY,
    decision VARCHAR(12) NOT NULL CHECK (decision IN ('accept','deny','revise')),
    state VARCHAR(24) NOT NULL CHECK (state IN ('processing','accepted','denied','revision_requested','unknown')),
    idempotency_key_sha256 CHAR(64) NOT NULL UNIQUE CHECK (idempotency_key_sha256 ~ '^[a-f0-9]{64}$'),
    request_sha256 CHAR(64) NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    claim_token_sha256 CHAR(64) NOT NULL CHECK (claim_token_sha256 ~ '^[a-f0-9]{64}$'),
    outcome JSONB,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT command_center_review_terminal_outcome CHECK (state='processing' OR outcome IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS command_center_reviews_state_lease_idx
    ON command_center_review_decisions (state,lease_expires_at);
INSERT INTO aigc_schema_migrations (version,migration_name)
VALUES (3,'003_command_center_state')
ON CONFLICT (version) DO NOTHING;
COMMIT;
