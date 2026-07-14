CREATE TABLE IF NOT EXISTS review_evidence_packets (
    packet_id TEXT PRIMARY KEY,
    quest_id TEXT NOT NULL,
    quest_revision INTEGER NOT NULL CHECK (quest_revision >= 1),
    exact_revision TEXT NOT NULL,
    packet_digest TEXT NOT NULL UNIQUE CHECK (packet_digest ~ '^[a-f0-9]{64}$'),
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[a-f0-9]{64}$'),
    identity_receipt_id TEXT NOT NULL,
    work_authorization_receipt_id TEXT NOT NULL,
    delivery_candidate BOOLEAN NOT NULL,
    recommended_decision TEXT NOT NULL CHECK (
        recommended_decision IN ('ACCEPTED_FOR_DELIVERY', 'REWORK_REQUIRED')
    ),
    packet_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    retention_class TEXT NOT NULL,
    UNIQUE (quest_id, quest_revision)
);

CREATE TABLE IF NOT EXISTS review_judgment_receipts (
    judgment_id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL UNIQUE REFERENCES review_evidence_packets(packet_id),
    quest_id TEXT NOT NULL,
    quest_revision INTEGER NOT NULL CHECK (quest_revision >= 1),
    exact_revision TEXT NOT NULL,
    identity_receipt_id TEXT NOT NULL,
    authorization_receipt_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('ACCEPTED_FOR_DELIVERY', 'REWORK_REQUIRED')
    ),
    judgment_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TRIGGER review_evidence_packets_no_mutation
BEFORE UPDATE OR DELETE ON review_evidence_packets
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();

CREATE TRIGGER review_judgment_receipts_no_mutation
BEFORE UPDATE OR DELETE ON review_judgment_receipts
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();

CREATE INDEX IF NOT EXISTS idx_review_packets_quest
ON review_evidence_packets(quest_id, quest_revision);

CREATE INDEX IF NOT EXISTS idx_review_packets_created
ON review_evidence_packets(created_at);

CREATE INDEX IF NOT EXISTS idx_review_judgments_quest
ON review_judgment_receipts(quest_id, quest_revision);
