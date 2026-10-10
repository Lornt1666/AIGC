CREATE TABLE IF NOT EXISTS aigc_artifact_metadata (
    id BIGSERIAL PRIMARY KEY,
    logical_key TEXT NOT NULL,
    version_id TEXT NOT NULL,
    object_key TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    media_type TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    provenance TEXT NOT NULL,
    operation_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT aigc_artifact_version_nonempty CHECK (length(version_id) > 0),
    CONSTRAINT aigc_artifact_operation_nonempty CHECK (length(operation_id) > 0)
);

CREATE INDEX IF NOT EXISTS aigc_artifact_logical_latest_idx
    ON aigc_artifact_metadata (logical_key, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS aigc_artifact_digest_idx
    ON aigc_artifact_metadata (sha256);

COMMENT ON TABLE aigc_artifact_metadata IS
    'Authoritative artifact metadata; S3 object existence alone never grants authority.';
COMMENT ON COLUMN aigc_artifact_metadata.version_id IS
    'Exact S3 VersionId returned by a versioned bucket; null/unversioned writes are rejected.';
