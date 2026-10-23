-- RX-148 persistent receipt-claim ledger. Apply under the migration identity.
SET ROLE aigc_owner;
CREATE TABLE IF NOT EXISTS aigc_receipt_claims (
  receipt_id TEXT PRIMARY KEY,
  payload_sha256 CHAR(64) NOT NULL,
  purpose TEXT NOT NULL,
  issuer TEXT NOT NULL,
  candidate_sha CHAR(40),
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  observation_count BIGINT NOT NULL DEFAULT 1 CHECK (observation_count >= 1)
);
CREATE INDEX IF NOT EXISTS aigc_receipt_claims_candidate_idx ON aigc_receipt_claims(candidate_sha, purpose);
RESET ROLE;
GRANT SELECT, INSERT, UPDATE ON aigc_receipt_claims TO aigc_receipt_verifier;
INSERT INTO aigc_schema_migrations(version) VALUES ('002_receipt_claims') ON CONFLICT DO NOTHING;
