-- Durable, idempotent dead-letter disposition ledger. Apply as the migration identity.
SET ROLE aigc_owner;
CREATE TABLE IF NOT EXISTS aigc_dead_letters (
  source_stream TEXT NOT NULL,
  source_stream_id TEXT NOT NULL,
  event_id TEXT,
  payload TEXT NOT NULL,
  failure_type TEXT NOT NULL,
  delivery_count INTEGER NOT NULL CHECK (delivery_count >= 1),
  disposition TEXT NOT NULL DEFAULT 'MANUAL_REVIEW_REQUIRED'
    CHECK (disposition = 'MANUAL_REVIEW_REQUIRED'),
  redis_dlq_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  dlq_published_at TIMESTAMPTZ,
  PRIMARY KEY (source_stream, source_stream_id)
);
CREATE INDEX IF NOT EXISTS aigc_dead_letters_pending_idx
  ON aigc_dead_letters(created_at) WHERE dlq_published_at IS NULL;
RESET ROLE;
GRANT SELECT, INSERT, UPDATE ON aigc_dead_letters TO aigc_app;
INSERT INTO aigc_schema_migrations(version)
  VALUES ('003_dead_letter_ledger') ON CONFLICT DO NOTHING;
