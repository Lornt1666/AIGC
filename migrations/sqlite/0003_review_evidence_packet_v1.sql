CREATE TABLE IF NOT EXISTS review_evidence_packets (
    packet_id TEXT PRIMARY KEY,
    quest_id TEXT NOT NULL,
    quest_revision INTEGER NOT NULL CHECK (quest_revision >= 1),
    exact_revision TEXT NOT NULL,
    packet_digest TEXT NOT NULL UNIQUE,
    request_digest TEXT NOT NULL,
    identity_receipt_id TEXT NOT NULL,
    work_authorization_receipt_id TEXT NOT NULL,
    delivery_candidate INTEGER NOT NULL CHECK (delivery_candidate IN (0, 1)),
    recommended_decision TEXT NOT NULL CHECK (
        recommended_decision IN ('ACCEPTED_FOR_DELIVERY', 'REWORK_REQUIRED')
    ),
    packet_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    retention_class TEXT NOT NULL,
    UNIQUE (quest_id, quest_revision)
);

CREATE TABLE IF NOT EXISTS review_judgment_receipts (
    judgment_id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL UNIQUE,
    quest_id TEXT NOT NULL,
    quest_revision INTEGER NOT NULL CHECK (quest_revision >= 1),
    exact_revision TEXT NOT NULL,
    identity_receipt_id TEXT NOT NULL,
    authorization_receipt_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('ACCEPTED_FOR_DELIVERY', 'REWORK_REQUIRED')
    ),
    judgment_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (packet_id) REFERENCES review_evidence_packets(packet_id)
);

CREATE TRIGGER IF NOT EXISTS review_evidence_packets_no_update
BEFORE UPDATE ON review_evidence_packets
BEGIN
    SELECT RAISE(ABORT, 'review evidence packets are append-only');
END;

CREATE TRIGGER IF NOT EXISTS review_evidence_packets_no_delete
BEFORE DELETE ON review_evidence_packets
BEGIN
    SELECT RAISE(ABORT, 'review evidence packets are append-only');
END;

CREATE TRIGGER IF NOT EXISTS review_judgment_receipts_no_update
BEFORE UPDATE ON review_judgment_receipts
BEGIN
    SELECT RAISE(ABORT, 'review judgment receipts are append-only');
END;

CREATE TRIGGER IF NOT EXISTS review_judgment_receipts_no_delete
BEFORE DELETE ON review_judgment_receipts
BEGIN
    SELECT RAISE(ABORT, 'review judgment receipts are append-only');
END;

CREATE INDEX IF NOT EXISTS idx_review_packets_quest
ON review_evidence_packets(quest_id, quest_revision);

CREATE INDEX IF NOT EXISTS idx_review_packets_created
ON review_evidence_packets(created_at);

CREATE INDEX IF NOT EXISTS idx_review_judgments_quest
ON review_judgment_receipts(quest_id, quest_revision);
