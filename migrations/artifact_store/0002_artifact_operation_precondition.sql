-- Bind each idempotent artifact operation to the compare-and-set precondition it first used.
-- Existing rows are legacy/unbound; no production deployment is approved until these are reconciled.
ALTER TABLE aigc_artifact_metadata
    ADD COLUMN IF NOT EXISTS expected_current_version_id TEXT;

COMMENT ON COLUMN aigc_artifact_metadata.expected_current_version_id IS
    'Original expected current artifact version for this operation; NULL denotes an initial write.';
