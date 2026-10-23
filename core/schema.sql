-- Reference schema for the AIGC durable ledger. Apply with a migration runner.
-- PostgreSQL is authoritative; Redis Streams is transport only.
CREATE TABLE IF NOT EXISTS aigc_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum CHAR(64) NOT NULL
);
