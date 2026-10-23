-- AIGC runtime schema migration 001. Run as a privileged migration identity, never as the API role.
CREATE TABLE IF NOT EXISTS aigc_schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
SET ROLE aigc_owner;
CREATE TABLE IF NOT EXISTS aigc_tasks (
  task_id UUID PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  contract_version TEXT NOT NULL,
  project_id TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  status TEXT NOT NULL,
  hop_count INTEGER NOT NULL DEFAULT 0 CHECK (hop_count BETWEEN 0 AND 10),
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS aigc_events (
  event_id UUID PRIMARY KEY,
  task_id UUID NOT NULL REFERENCES aigc_tasks(task_id),
  sequence BIGINT NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  payload_sha256 CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(task_id, sequence)
);
CREATE TABLE IF NOT EXISTS aigc_outbox (
  event_id UUID PRIMARY KEY REFERENCES aigc_events(event_id),
  stream_id TEXT,
  published_at TIMESTAMPTZ,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS aigc_consumed_events (
  consumer_name TEXT NOT NULL,
  event_id UUID NOT NULL,
  consumed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(consumer_name, event_id)
);
CREATE TABLE IF NOT EXISTS aigc_saga_steps (
  task_id UUID NOT NULL REFERENCES aigc_tasks(task_id),
  step_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  status TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  receipt JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(task_id, step_id),
  UNIQUE(task_id, ordinal)
);
CREATE INDEX IF NOT EXISTS aigc_outbox_pending_idx ON aigc_outbox(created_at) WHERE published_at IS NULL;
CREATE INDEX IF NOT EXISTS aigc_events_task_idx ON aigc_events(task_id, sequence);
CREATE OR REPLACE FUNCTION aigc_reject_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'aigc_events is append-only; UPDATE/DELETE is prohibited';
END;
$$;
DROP TRIGGER IF EXISTS aigc_events_no_update ON aigc_events;
CREATE TRIGGER aigc_events_no_update BEFORE UPDATE OR DELETE ON aigc_events
  FOR EACH ROW EXECUTE FUNCTION aigc_reject_event_mutation();
RESET ROLE;
GRANT USAGE ON SCHEMA public TO aigc_app;
GRANT SELECT ON aigc_schema_migrations TO aigc_app;
GRANT SELECT, INSERT, UPDATE ON aigc_tasks TO aigc_app;
GRANT SELECT, INSERT ON aigc_events TO aigc_app;
GRANT SELECT, INSERT, UPDATE ON aigc_outbox TO aigc_app;
GRANT SELECT, INSERT ON aigc_consumed_events TO aigc_app;
GRANT SELECT, INSERT, UPDATE ON aigc_saga_steps TO aigc_app;
INSERT INTO aigc_schema_migrations(version) VALUES ('001_runtime') ON CONFLICT DO NOTHING;
