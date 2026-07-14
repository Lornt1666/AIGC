CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL,
    checksum TEXT NOT NULL CHECK (checksum ~ '^[a-f0-9]{64}$')
);

CREATE TABLE IF NOT EXISTS records (
    collection TEXT NOT NULL,
    record_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    payload_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revocation_reason TEXT,
    retention_state TEXT NOT NULL DEFAULT 'ACTIVE',
    PRIMARY KEY (collection, record_id)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    scope TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[a-f0-9]{64}$'),
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (scope, idempotency_key)
);

CREATE TABLE IF NOT EXISTS authorization_receipts (
    receipt_id TEXT PRIMARY KEY,
    exact_revision TEXT NOT NULL,
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[a-f0-9]{64}$'),
    receipt_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    exact_revision TEXT NOT NULL,
    request_digest TEXT,
    payload_json JSONB NOT NULL,
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE CHECK (event_hash ~ '^[a-f0-9]{64}$'),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE OR REPLACE FUNCTION aigc_reject_append_only_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'AIGC append-only relation % cannot be updated or deleted', TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER authorization_receipts_no_mutation
BEFORE UPDATE OR DELETE ON authorization_receipts
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();

CREATE TRIGGER audit_events_no_mutation
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();

CREATE INDEX IF NOT EXISTS idx_records_collection ON records(collection);
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at);
