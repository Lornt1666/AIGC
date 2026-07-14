CREATE TABLE IF NOT EXISTS identity_evidence_receipts (
    receipt_id TEXT PRIMARY KEY,
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[a-f0-9]{64}$'),
    replay_key_digest TEXT NOT NULL UNIQUE CHECK (replay_key_digest ~ '^[a-f0-9]{64}$'),
    result TEXT NOT NULL CHECK (result IN ('PERMIT', 'DENY')),
    reason_codes_json JSONB NOT NULL,
    provider_class TEXT,
    provider_binding_id TEXT,
    assertion_id TEXT,
    principal_id TEXT,
    membership_id TEXT,
    session_id TEXT,
    tenant_id TEXT,
    project_id TEXT,
    exact_revision TEXT NOT NULL,
    receipt_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    retention_class TEXT NOT NULL
);

CREATE TRIGGER identity_evidence_receipts_no_mutation
BEFORE UPDATE OR DELETE ON identity_evidence_receipts
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();

CREATE INDEX IF NOT EXISTS idx_identity_receipts_principal
ON identity_evidence_receipts(principal_id);

CREATE INDEX IF NOT EXISTS idx_identity_receipts_session
ON identity_evidence_receipts(session_id);

CREATE INDEX IF NOT EXISTS idx_identity_receipts_tenant_project
ON identity_evidence_receipts(tenant_id, project_id);

CREATE INDEX IF NOT EXISTS idx_identity_receipts_created
ON identity_evidence_receipts(created_at);
