ALTER TABLE grant_applications
ADD COLUMN revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1);

ALTER TABLE grant_applications
ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';

UPDATE grant_applications
SET updated_at = created_at
WHERE updated_at = '';

ALTER TABLE grant_audit_events
ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE grant_audit_events
ADD COLUMN previous_event_hash TEXT;

ALTER TABLE grant_audit_events
ADD COLUMN event_hash TEXT;

CREATE TABLE grant_operator_reviews (
    review_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES grant_applications(application_id),
    application_revision INTEGER NOT NULL CHECK (application_revision >= 2),
    created_at TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('APPROVE_LOCAL_EXPORT', 'RETURN_FOR_REVISION')
    ),
    review_digest TEXT NOT NULL,
    review_json TEXT NOT NULL,
    UNIQUE(application_id, application_revision)
);

CREATE TRIGGER grant_operator_reviews_no_replace
BEFORE INSERT ON grant_operator_reviews
WHEN EXISTS (
    SELECT 1
    FROM grant_operator_reviews
    WHERE review_id = NEW.review_id
       OR (
           application_id = NEW.application_id
           AND application_revision = NEW.application_revision
       )
)
BEGIN
    SELECT RAISE(ABORT, 'grant operator reviews are append-only');
END;

CREATE TRIGGER grant_operator_reviews_no_update
BEFORE UPDATE ON grant_operator_reviews
BEGIN
    SELECT RAISE(ABORT, 'grant operator reviews are append-only');
END;

CREATE TRIGGER grant_operator_reviews_no_delete
BEFORE DELETE ON grant_operator_reviews
BEGIN
    SELECT RAISE(ABORT, 'grant operator reviews are append-only');
END;
