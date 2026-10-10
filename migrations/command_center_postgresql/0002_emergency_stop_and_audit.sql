ALTER TABLE command_center_runs
    ADD COLUMN IF NOT EXISTS stop_epoch BIGINT NOT NULL DEFAULT 0 CHECK (stop_epoch >= 0);

ALTER TABLE command_center_runs DROP CONSTRAINT IF EXISTS command_center_runs_status_check;
ALTER TABLE command_center_runs ADD CONSTRAINT command_center_runs_status_check
    CHECK (status IN ('queued','running','completed','failed','timed_out','unknown','stopped'));

ALTER TABLE command_center_runs DROP CONSTRAINT IF EXISTS command_center_run_complete_matches_status;
ALTER TABLE command_center_runs ADD CONSTRAINT command_center_run_complete_matches_status
    CHECK (complete = (status IN ('completed','failed','timed_out','unknown','stopped')));

CREATE TABLE IF NOT EXISTS command_center_control_state (
    singleton_id SMALLINT PRIMARY KEY CHECK (singleton_id = 1),
    emergency_stop_active BOOLEAN NOT NULL DEFAULT FALSE,
    stop_epoch BIGINT NOT NULL DEFAULT 0 CHECK (stop_epoch >= 0),
    reason TEXT NOT NULL DEFAULT '',
    actor_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO command_center_control_state (singleton_id) VALUES (1)
    ON CONFLICT (singleton_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS command_center_control_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type IN ('activated','cleared')),
    actor_id TEXT NOT NULL,
    stop_epoch BIGINT NOT NULL CHECK (stop_epoch >= 0),
    reason_sha256 CHAR(64) NOT NULL CHECK (reason_sha256 ~ '^[a-f0-9]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS command_center_run_reconciliations (
    reconciliation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    expected_version BIGINT NOT NULL CHECK (expected_version >= 1),
    actor_id TEXT NOT NULL,
    confirmation_phrase_sha256 CHAR(64) NOT NULL
        CHECK (confirmation_phrase_sha256 ~ '^[a-f0-9]{64}$'),
    disposition TEXT NOT NULL CHECK (disposition = 'failed'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, expected_version)
);

CREATE OR REPLACE FUNCTION aigc_command_center_reject_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'append-only command-center audit records cannot be changed';
END;
$$;

DROP TRIGGER IF EXISTS command_center_control_events_no_mutation ON command_center_control_events;
CREATE TRIGGER command_center_control_events_no_mutation
    BEFORE UPDATE OR DELETE ON command_center_control_events
    FOR EACH ROW EXECUTE FUNCTION aigc_command_center_reject_append_only_mutation();

DROP TRIGGER IF EXISTS command_center_run_reconciliations_no_mutation ON command_center_run_reconciliations;
CREATE TRIGGER command_center_run_reconciliations_no_mutation
    BEFORE UPDATE OR DELETE ON command_center_run_reconciliations
    FOR EACH ROW EXECUTE FUNCTION aigc_command_center_reject_append_only_mutation();

CREATE INDEX IF NOT EXISTS command_center_control_events_created_idx
    ON command_center_control_events (created_at);
CREATE INDEX IF NOT EXISTS command_center_run_reconciliations_run_idx
    ON command_center_run_reconciliations (run_id, created_at);
