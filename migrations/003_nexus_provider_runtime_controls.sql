BEGIN;

CREATE TABLE IF NOT EXISTS nexus_runtime_control (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    emergency_active BOOLEAN NOT NULL DEFAULT FALSE,
    stop_epoch BIGINT NOT NULL DEFAULT 0 CHECK (stop_epoch >= 0),
    reason TEXT NOT NULL DEFAULT '',
    actor_principal_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO nexus_runtime_control(singleton)
VALUES (TRUE)
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS nexus_runtime_invocation (
    invocation_id TEXT PRIMARY KEY,
    principal TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    permit_id TEXT,
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    exact_revision TEXT NOT NULL,
    stop_epoch BIGINT NOT NULL CHECK (stop_epoch >= 0),
    state TEXT NOT NULL CHECK (state IN ('reserved','executing','completed','failed','timed_out','indeterminate')),
    reserved_usage_units BIGINT NOT NULL CHECK (reserved_usage_units >= 1),
    actual_usage_units BIGINT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    failure_reason TEXT,
    result_json JSONB,
    UNIQUE (principal, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_nexus_runtime_invocation_permit
    ON nexus_runtime_invocation(permit_id)
    WHERE permit_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_nexus_runtime_invocation_created
    ON nexus_runtime_invocation(created_at);

CREATE TABLE IF NOT EXISTS nexus_runtime_usage (
    scope_type TEXT NOT NULL CHECK (scope_type IN ('principal','global')),
    scope_id TEXT NOT NULL,
    window_kind TEXT NOT NULL CHECK (window_kind IN ('minute','day')),
    window_start TIMESTAMPTZ NOT NULL,
    run_count BIGINT NOT NULL DEFAULT 0 CHECK (run_count >= 0),
    reserved_usage_units BIGINT NOT NULL DEFAULT 0 CHECK (reserved_usage_units >= 0),
    actual_usage_units BIGINT NOT NULL DEFAULT 0 CHECK (actual_usage_units >= 0),
    PRIMARY KEY (scope_type, scope_id, window_kind, window_start)
);

CREATE TABLE IF NOT EXISTS nexus_runtime_permit_usage (
    permit_id TEXT PRIMARY KEY,
    invocation_count BIGINT NOT NULL DEFAULT 0 CHECK (invocation_count >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;
