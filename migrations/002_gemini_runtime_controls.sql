BEGIN;

CREATE TABLE IF NOT EXISTS gemini_runtime_control (
    singleton_id SMALLINT PRIMARY KEY
        CHECK (singleton_id = 1),
    emergency_active BOOLEAN NOT NULL DEFAULT FALSE,
    stop_epoch BIGINT NOT NULL DEFAULT 0
        CHECK (stop_epoch >= 0),
    reason TEXT NOT NULL DEFAULT '',
    actor_principal_id VARCHAR(128),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO gemini_runtime_control (
    singleton_id,
    emergency_active,
    stop_epoch,
    reason,
    actor_principal_id
)
VALUES (1, FALSE, 0, '', NULL)
ON CONFLICT (singleton_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS gemini_run_reservations (
    run_id VARCHAR(100) PRIMARY KEY,
    principal_id VARCHAR(128) NOT NULL,
    idempotency_key_sha256 CHAR(64) NOT NULL
        CHECK (idempotency_key_sha256 ~ '^[a-f0-9]{64}$'),
    request_sha256 CHAR(64) NOT NULL
        CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    model VARCHAR(200) NOT NULL
        CHECK (length(model) > 0),
    source_revision VARCHAR(128) NOT NULL DEFAULT '',
    stop_epoch BIGINT NOT NULL
        CHECK (stop_epoch >= 0),
    state VARCHAR(16) NOT NULL
        CHECK (
            state IN (
                'reserved',
                'executing',
                'completed',
                'failed',
                'stopped',
                'evidence_missing'
            )
        ),
    reserved_tokens BIGINT NOT NULL
        CHECK (reserved_tokens > 0),
    actual_tokens BIGINT
        CHECK (actual_tokens IS NULL OR actual_tokens >= 0),
    minute_window_start TIMESTAMPTZ NOT NULL,
    day_window_start TIMESTAMPTZ NOT NULL,
    execution_event_id VARCHAR(128),
    evidence_object_uri TEXT,
    evidence_generation BIGINT
        CHECK (
            evidence_generation IS NULL
            OR evidence_generation > 0
        ),
    decision_event_id VARCHAR(128),
    decision_object_uri TEXT,
    decision_generation BIGINT
        CHECK (
            decision_generation IS NULL
            OR decision_generation > 0
        ),
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT gemini_run_idempotency_unique
        UNIQUE (principal_id, idempotency_key_sha256),
    CONSTRAINT gemini_run_evidence_pair
        CHECK (
            (
                evidence_object_uri IS NULL
                AND evidence_generation IS NULL
            )
            OR
            (
                evidence_object_uri LIKE 'gs://%'
                AND evidence_generation IS NOT NULL
            )
        ),
    CONSTRAINT gemini_completed_evidence_required
        CHECK (
            state <> 'completed'
            OR (
                execution_event_id IS NOT NULL
                AND evidence_object_uri LIKE 'gs://%'
                AND evidence_generation IS NOT NULL
            )
        ),
    CONSTRAINT gemini_decision_receipt_complete
        CHECK (
            (
                decision_event_id IS NULL
                AND decision_object_uri IS NULL
                AND decision_generation IS NULL
            )
            OR (
                state = 'completed'
                AND decision_event_id IS NOT NULL
                AND decision_object_uri LIKE 'gs://%'
                AND decision_generation IS NOT NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS gemini_run_reservations_state_idx
    ON gemini_run_reservations (state, updated_at);

CREATE INDEX IF NOT EXISTS gemini_run_reservations_request_idx
    ON gemini_run_reservations (request_sha256);

CREATE TABLE IF NOT EXISTS gemini_usage_windows (
    scope_type VARCHAR(16) NOT NULL
        CHECK (scope_type IN ('principal', 'global')),
    scope_id VARCHAR(128) NOT NULL,
    window_kind VARCHAR(16) NOT NULL
        CHECK (window_kind IN ('minute', 'day')),
    window_start TIMESTAMPTZ NOT NULL,
    run_count BIGINT NOT NULL DEFAULT 0
        CHECK (run_count >= 0),
    reserved_tokens BIGINT NOT NULL DEFAULT 0
        CHECK (reserved_tokens >= 0),
    actual_tokens BIGINT NOT NULL DEFAULT 0
        CHECK (actual_tokens >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        scope_type,
        scope_id,
        window_kind,
        window_start
    )
);

COMMENT ON TABLE gemini_runtime_control IS
    'Durable singleton emergency-stop state. Every activation and clear increments stop_epoch.';

COMMENT ON TABLE gemini_run_reservations IS
    'Single-flight Gemini run reservations keyed by stable principal and a one-way idempotency-key digest.';

COMMENT ON COLUMN gemini_run_reservations.idempotency_key_sha256 IS
    'SHA-256 of the caller idempotency key; the raw credential-like key is never persisted.';

COMMENT ON COLUMN gemini_run_reservations.actual_tokens IS
    'Observed provider usage. NULL means unavailable; accounting retains the full reservation.';

COMMENT ON COLUMN gemini_run_reservations.decision_event_id IS
    'Durable completion marker for one quarantined operator-decision evidence object.';

COMMENT ON TABLE gemini_usage_windows IS
    'Atomic request and token reservations. Reserved tokens are never refunded within the window.';

COMMIT;
