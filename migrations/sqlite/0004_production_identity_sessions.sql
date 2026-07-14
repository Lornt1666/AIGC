CREATE TABLE IF NOT EXISTS provider_subject_bindings (
    provider_binding_id TEXT NOT NULL,
    provider_subject TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    membership_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'SUSPENDED', 'REVOKED')),
    evidence_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    PRIMARY KEY (provider_binding_id, provider_subject)
);

CREATE TABLE IF NOT EXISTS provider_subject_revocation_state (
    provider_binding_id TEXT NOT NULL,
    provider_subject TEXT NOT NULL,
    disabled INTEGER NOT NULL CHECK (disabled IN (0, 1)),
    valid_after TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    PRIMARY KEY (provider_binding_id, provider_subject)
);

CREATE TABLE IF NOT EXISTS production_identity_sessions (
    session_id TEXT PRIMARY KEY,
    credential_digest TEXT NOT NULL UNIQUE CHECK (length(credential_digest) = 64),
    principal_id TEXT NOT NULL,
    membership_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'ROTATED', 'REVOKED', 'EXPIRED')),
    authentication_assurance TEXT NOT NULL CHECK (authentication_assurance IN ('AAL0', 'AAL1', 'AAL2', 'AAL3')),
    issued_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    idle_expires_at TEXT NOT NULL,
    absolute_expires_at TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    evidence_ids_json TEXT NOT NULL,
    rotated_from_session_id TEXT REFERENCES production_identity_sessions(session_id),
    revoked_at TEXT,
    revocation_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_provider_subject_principal
ON provider_subject_bindings(principal_id, state);

CREATE INDEX IF NOT EXISTS idx_provider_subject_tenant_project
ON provider_subject_bindings(tenant_id, project_id, state);

CREATE INDEX IF NOT EXISTS idx_provider_revocation_checked
ON provider_subject_revocation_state(checked_at);

CREATE INDEX IF NOT EXISTS idx_production_sessions_principal
ON production_identity_sessions(principal_id, state);

CREATE INDEX IF NOT EXISTS idx_production_sessions_tenant_project
ON production_identity_sessions(tenant_id, project_id, state);

CREATE INDEX IF NOT EXISTS idx_production_sessions_expiry
ON production_identity_sessions(idle_expires_at, absolute_expires_at);
