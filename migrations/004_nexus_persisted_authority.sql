BEGIN;

CREATE TABLE IF NOT EXISTS nexus_canary_authority_claim (
    permit_id TEXT PRIMARY KEY,
    attestation_id TEXT NOT NULL UNIQUE,
    attestation_sha256 TEXT NOT NULL UNIQUE CHECK (attestation_sha256 ~ '^[a-f0-9]{64}$'),
    execution_nonce TEXT NOT NULL UNIQUE CHECK (execution_nonce ~ '^[a-f0-9]{64}$'),
    procurement_sha256 TEXT NOT NULL CHECK (procurement_sha256 ~ '^[a-f0-9]{64}$'),
    deployment_sha256 TEXT NOT NULL CHECK (deployment_sha256 ~ '^[a-f0-9]{64}$'),
    plan_sha256 TEXT NOT NULL CHECK (plan_sha256 ~ '^[a-f0-9]{64}$'),
    governance_decision_sha256 TEXT NOT NULL CHECK (governance_decision_sha256 ~ '^[a-f0-9]{64}$'),
    execution_permit_sha256 TEXT NOT NULL UNIQUE CHECK (execution_permit_sha256 ~ '^[a-f0-9]{64}$'),
    request_digest TEXT NOT NULL UNIQUE CHECK (request_digest ~ '^[a-f0-9]{64}$'),
    principal TEXT NOT NULL,
    exact_revision TEXT NOT NULL CHECK (exact_revision ~ '^[a-f0-9]{40}$'),
    job_name TEXT NOT NULL,
    execution_name TEXT NOT NULL UNIQUE,
    claimed_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nexus_canary_authority_claimed_at
    ON nexus_canary_authority_claim(claimed_at);

COMMIT;
