CREATE TABLE IF NOT EXISTS command_center_runs (
    run_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    idempotency_key_sha256 CHAR(64) NOT NULL CHECK (idempotency_key_sha256 ~ '^[a-f0-9]{64}$'),
    request_sha256 CHAR(64) NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','timed_out','unknown')),
    steps JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(steps) = 'array'),
    current_step TEXT NOT NULL DEFAULT '',
    complete BOOLEAN NOT NULL DEFAULT FALSE,
    lease_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version BIGINT NOT NULL DEFAULT 1 CHECK (version >= 1),
    CONSTRAINT command_center_run_idempotency_unique UNIQUE (actor_id, idempotency_key_sha256),
    CONSTRAINT command_center_run_complete_matches_status
      CHECK (complete = (status IN ('completed','failed','timed_out','unknown')))
);
CREATE UNIQUE INDEX IF NOT EXISTS command_center_one_active_run
  ON command_center_runs ((1)) WHERE status IN ('queued','running','unknown');
CREATE INDEX IF NOT EXISTS command_center_runs_updated_idx ON command_center_runs (updated_at);

CREATE TABLE IF NOT EXISTS command_center_review_decisions (
    action_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    idempotency_key_sha256 CHAR(64) NOT NULL CHECK (idempotency_key_sha256 ~ '^[a-f0-9]{64}$'),
    request_sha256 CHAR(64) NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    decision_type TEXT NOT NULL CHECK (decision_type IN ('accept','deny','revise')),
    state TEXT NOT NULL CHECK (state IN ('claimed','completed','unknown')),
    result_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT command_center_review_idempotency_unique UNIQUE (actor_id, idempotency_key_sha256),
    CONSTRAINT command_center_review_result_matches_state
      CHECK ((state = 'completed' AND result_json IS NOT NULL) OR (state <> 'completed' AND result_json IS NULL))
);
CREATE INDEX IF NOT EXISTS command_center_review_decisions_updated_idx ON command_center_review_decisions (updated_at);
