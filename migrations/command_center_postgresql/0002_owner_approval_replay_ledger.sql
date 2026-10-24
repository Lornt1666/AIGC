-- Durable, single-use owner approval replay protection.
-- Apply through the controlled database migration process before enabling verification.
CREATE TABLE IF NOT EXISTS aigc_owner_approval_replay (
    approval_id TEXT PRIMARY KEY,
    nonce TEXT NOT NULL UNIQUE,
    payload_sha256 CHAR(64) NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT aigc_owner_approval_replay_payload_sha256_format
        CHECK (payload_sha256 ~ '^[a-f0-9]{64}$')
);

COMMENT ON TABLE aigc_owner_approval_replay IS
    'Single-use signed owner approvals; uniqueness constraints provide cross-replica replay protection.';
