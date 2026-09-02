ALTER TABLE grant_operator_reviews
ADD COLUMN approved_artifact_digest TEXT;

CREATE TRIGGER grant_operator_reviews_approved_export_digest_required
BEFORE INSERT ON grant_operator_reviews
WHEN NEW.decision = 'APPROVE_LOCAL_EXPORT'
 AND (
    NEW.approved_artifact_digest IS NULL
    OR length(NEW.approved_artifact_digest) != 64
 )
BEGIN
    SELECT RAISE(ABORT, 'approved local exports require an artifact digest');
END;

CREATE TABLE grant_local_export_artifacts (
    export_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES grant_applications(application_id),
    application_revision INTEGER NOT NULL CHECK (application_revision >= 2),
    approved_review_id TEXT NOT NULL UNIQUE REFERENCES grant_operator_reviews(review_id),
    created_at TEXT NOT NULL,
    artifact_digest TEXT NOT NULL,
    artifact_json TEXT NOT NULL,
    UNIQUE(application_id, application_revision)
);

CREATE TRIGGER grant_local_export_artifacts_no_replace
BEFORE INSERT ON grant_local_export_artifacts
WHEN EXISTS (
    SELECT 1
    FROM grant_local_export_artifacts
    WHERE export_id = NEW.export_id
       OR (
            application_id = NEW.application_id
            AND application_revision = NEW.application_revision
       )
       OR approved_review_id = NEW.approved_review_id
)
BEGIN
    SELECT RAISE(ABORT, 'grant local export artifacts are append-only');
END;

CREATE TRIGGER grant_local_export_artifacts_no_update
BEFORE UPDATE ON grant_local_export_artifacts
BEGIN
    SELECT RAISE(ABORT, 'grant local export artifacts are append-only');
END;

CREATE TRIGGER grant_local_export_artifacts_no_delete
BEFORE DELETE ON grant_local_export_artifacts
BEGIN
    SELECT RAISE(ABORT, 'grant local export artifacts are append-only');
END;

CREATE TRIGGER grant_applications_approved_no_update
BEFORE UPDATE ON grant_applications
WHEN OLD.lifecycle_state = 'LOCAL_EXPORT_APPROVED'
BEGIN
    SELECT RAISE(ABORT, 'approved grant applications are immutable');
END;

CREATE TRIGGER grant_applications_approved_no_delete
BEFORE DELETE ON grant_applications
WHEN OLD.lifecycle_state = 'LOCAL_EXPORT_APPROVED'
BEGIN
    SELECT RAISE(ABORT, 'approved grant applications are immutable');
END;

CREATE TRIGGER grant_applications_no_replace
BEFORE INSERT ON grant_applications
WHEN EXISTS (
    SELECT 1
    FROM grant_applications
    WHERE application_id = NEW.application_id
)
BEGIN
    SELECT RAISE(ABORT, 'grant applications cannot be replaced');
END;
