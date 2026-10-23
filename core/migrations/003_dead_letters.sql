-- RX-162 durable, deduplicated dead-letter ledger and Redis projection receipt.
SET ROLE aigc_owner;
CREATE TABLE IF NOT EXISTS aigc_dead_letters (
  disposition_id CHAR(64) PRIMARY KEY,
  source_stream TEXT NOT NULL,
  source_stream_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  payload_sha256 CHAR(64) NOT NULL,
  failure_type TEXT NOT NULL,
  delivery_count INTEGER NOT NULL CHECK (delivery_count >= 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ,
  UNIQUE(source_stream, source_stream_id)
);
CREATE INDEX IF NOT EXISTS aigc_dead_letters_pending_idx
  ON aigc_dead_letters(created_at) WHERE published_at IS NULL;
RESET ROLE;
GRANT SELECT, INSERT, UPDATE ON aigc_dead_letters TO aigc_app;
INSERT INTO aigc_schema_migrations(version) VALUES ('003_dead_letters') ON CONFLICT DO NOTHING;
