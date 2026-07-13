CREATE TABLE IF NOT EXISTS identity_evidence_receipts (
    receipt_id TEXT PRIMARY KEY,
    request_digest TEXT NOT NULL,
    replay_key_digest TEXT NOT NULL UNIQUE,
    result TEXT NOT NULL CHECK (result IN ('PERMIT', 'DENY')),
    reason_codes_json TEXT NOT NULL,
    provider_class TEXT,
    provider_binding_id TEXT,
    assertion_id TEXT,
    principal_id TEXT,
    membership_id TEXT,
    session_id TEXT,
    tenant_id TEXT,
    project_id TEXT,
    exact_revision TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    retention_class TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS identity_evidence_receipts_no_update
BEFORE UPDATE ON identity_evidence_receipts
BEGIN
    SELECT RAISE(ABORT, 'identity evidence receipts are append-only');
END;

CREATE TRIGGER IF NOT EXISTS identity_evidence_receipts_no_delete
BEFORE DELETE ON identity_evidence_receipts
BEGIN
    SELECT RAISE(ABORT, 'identity evidence receipts are append-only');
END;

CREATE INDEX IF NOT EXISTS idx_identity_receipts_principal
ON identity_evidence_receipts(principal_id);

CREATE INDEX IF NOT EXISTS idx_identity_receipts_session
ON identity_evidence_receipts(session_id);

CREATE INDEX IF NOT EXISTS idx_identity_receipts_tenant_project
ON identity_evidence_receipts(tenant_id, project_id);

CREATE INDEX IF NOT EXISTS idx_identity_receipts_created
ON identity_evidence_receipts(created_at);
