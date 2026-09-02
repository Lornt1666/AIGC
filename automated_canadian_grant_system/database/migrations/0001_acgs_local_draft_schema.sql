PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS grant_applications (
    application_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    external_submission_performed INTEGER NOT NULL DEFAULT 0 CHECK (external_submission_performed = 0)
);

CREATE TABLE IF NOT EXISTS grant_audit_events (
    event_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES grant_applications(application_id),
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_digest TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS grant_audit_events_no_replace
BEFORE INSERT ON grant_audit_events
WHEN EXISTS (
    SELECT 1
    FROM grant_audit_events
    WHERE event_id = NEW.event_id
)
BEGIN
    SELECT RAISE(ABORT, 'grant audit events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS grant_audit_events_no_update
BEFORE UPDATE ON grant_audit_events
BEGIN
    SELECT RAISE(ABORT, 'grant audit events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS grant_audit_events_no_delete
BEFORE DELETE ON grant_audit_events
BEGIN
    SELECT RAISE(ABORT, 'grant audit events are append-only');
END;
