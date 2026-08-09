CREATE TABLE IF NOT EXISTS revenue_omega_agreements (
    agreement_id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    employer_id TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    service_type TEXT NOT NULL,
    payer_model TEXT NOT NULL,
    jurisdiction_decision_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    agreement_hash TEXT NOT NULL UNIQUE CHECK (agreement_hash ~ '^[a-f0-9]{64}$'),
    agreement_json JSONB NOT NULL,
    active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS revenue_omega_jurisdiction_decisions (
    decision_id TEXT PRIMARY KEY,
    jurisdiction TEXT NOT NULL,
    service_type TEXT NOT NULL,
    payer_model TEXT NOT NULL,
    allowed BOOLEAN NOT NULL,
    decision_hash TEXT NOT NULL UNIQUE CHECK (decision_hash ~ '^[a-f0-9]{64}$'),
    decision_json JSONB NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS revenue_omega_placements (
    placement_id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL REFERENCES revenue_omega_agreements(agreement_id),
    employer_id TEXT NOT NULL,
    worker_reference TEXT NOT NULL,
    billing_period TEXT NOT NULL,
    currency TEXT NOT NULL,
    eligible_compensation NUMERIC(20,2) NOT NULL CHECK (eligible_compensation >= 0),
    placement_hash TEXT NOT NULL UNIQUE CHECK (placement_hash ~ '^[a-f0-9]{64}$'),
    placement_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS revenue_omega_compute_usage (
    usage_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    placement_id TEXT NOT NULL REFERENCES revenue_omega_placements(placement_id),
    provider TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    quantity NUMERIC(30,8) NOT NULL CHECK (quantity >= 0),
    unit_cost NUMERIC(20,2) NOT NULL CHECK (unit_cost >= 0),
    actual_cost NUMERIC(20,2) NOT NULL CHECK (actual_cost >= 0),
    currency TEXT NOT NULL,
    evidence_ref TEXT NOT NULL,
    usage_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS revenue_omega_billing_reservations (
    billing_idempotency_key TEXT PRIMARY KEY CHECK (billing_idempotency_key ~ '^[a-f0-9]{64}$'),
    agreement_id TEXT NOT NULL REFERENCES revenue_omega_agreements(agreement_id),
    placement_id TEXT NOT NULL REFERENCES revenue_omega_placements(placement_id),
    billing_period TEXT NOT NULL,
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[a-f0-9]{64}$'),
    decision_hash TEXT NOT NULL CHECK (decision_hash ~ '^[a-f0-9]{64}$'),
    reservation_state TEXT NOT NULL CHECK (reservation_state IN ('RESERVED', 'INVOICE_CREATED', 'VOIDED', 'RECONCILIATION_REQUIRED')),
    reservation_json JSONB NOT NULL,
    reserved_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS revenue_omega_commission_calculations (
    calculation_id TEXT PRIMARY KEY,
    billing_idempotency_key TEXT NOT NULL UNIQUE REFERENCES revenue_omega_billing_reservations(billing_idempotency_key),
    placement_id TEXT NOT NULL REFERENCES revenue_omega_placements(placement_id),
    agreement_id TEXT NOT NULL REFERENCES revenue_omega_agreements(agreement_id),
    finder_fee NUMERIC(20,2) NOT NULL CHECK (finder_fee >= 0),
    compute_cost NUMERIC(20,2) NOT NULL CHECK (compute_cost >= 0),
    compute_recovery NUMERIC(20,2) NOT NULL CHECK (compute_recovery >= 0),
    subtotal NUMERIC(20,2) NOT NULL CHECK (subtotal >= 0),
    currency TEXT NOT NULL,
    calculation_hash TEXT NOT NULL UNIQUE CHECK (calculation_hash ~ '^[a-f0-9]{64}$'),
    calculation_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS revenue_omega_invoice_events (
    sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    invoice_id TEXT NOT NULL,
    billing_idempotency_key TEXT NOT NULL REFERENCES revenue_omega_billing_reservations(billing_idempotency_key),
    event_type TEXT NOT NULL,
    invoice_hash TEXT CHECK (invoice_hash IS NULL OR invoice_hash ~ '^[a-f0-9]{64}$'),
    event_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS revenue_omega_payment_events (
    sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    invoice_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_event_id TEXT NOT NULL,
    provider_transaction_reference TEXT,
    amount NUMERIC(20,2) NOT NULL CHECK (amount >= 0),
    currency TEXT NOT NULL,
    payment_state TEXT NOT NULL,
    provider_envelope_hash TEXT NOT NULL CHECK (provider_envelope_hash ~ '^[a-f0-9]{64}$'),
    event_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (provider, provider_event_id)
);

CREATE TABLE IF NOT EXISTS revenue_omega_ledger_transactions (
    transaction_id TEXT PRIMARY KEY,
    reference_id TEXT NOT NULL,
    transaction_hash TEXT NOT NULL UNIQUE CHECK (transaction_hash ~ '^[a-f0-9]{64}$'),
    entries_json JSONB NOT NULL,
    debit_total NUMERIC(20,2) NOT NULL CHECK (debit_total >= 0),
    credit_total NUMERIC(20,2) NOT NULL CHECK (credit_total >= 0),
    currency TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (debit_total = credit_total)
);

CREATE TABLE IF NOT EXISTS revenue_omega_audit_events (
    sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE CHECK (event_hash ~ '^[a-f0-9]{64}$'),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TRIGGER revenue_omega_jurisdiction_decisions_no_mutation
BEFORE UPDATE OR DELETE ON revenue_omega_jurisdiction_decisions
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();
CREATE TRIGGER revenue_omega_compute_usage_no_mutation
BEFORE UPDATE OR DELETE ON revenue_omega_compute_usage
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();
CREATE TRIGGER revenue_omega_commission_calculations_no_mutation
BEFORE UPDATE OR DELETE ON revenue_omega_commission_calculations
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();
CREATE TRIGGER revenue_omega_invoice_events_no_mutation
BEFORE UPDATE OR DELETE ON revenue_omega_invoice_events
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();
CREATE TRIGGER revenue_omega_payment_events_no_mutation
BEFORE UPDATE OR DELETE ON revenue_omega_payment_events
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();
CREATE TRIGGER revenue_omega_ledger_transactions_no_mutation
BEFORE UPDATE OR DELETE ON revenue_omega_ledger_transactions
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();
CREATE TRIGGER revenue_omega_audit_events_no_mutation
BEFORE UPDATE OR DELETE ON revenue_omega_audit_events
FOR EACH ROW EXECUTE FUNCTION aigc_reject_append_only_mutation();

CREATE INDEX IF NOT EXISTS idx_revenue_omega_agreements_employer ON revenue_omega_agreements(employer_id);
CREATE INDEX IF NOT EXISTS idx_revenue_omega_placements_agreement ON revenue_omega_placements(agreement_id);
CREATE INDEX IF NOT EXISTS idx_revenue_omega_compute_placement ON revenue_omega_compute_usage(placement_id);
CREATE INDEX IF NOT EXISTS idx_revenue_omega_invoice_id ON revenue_omega_invoice_events(invoice_id);
CREATE INDEX IF NOT EXISTS idx_revenue_omega_payment_invoice ON revenue_omega_payment_events(invoice_id);
CREATE INDEX IF NOT EXISTS idx_revenue_omega_audit_aggregate ON revenue_omega_audit_events(aggregate_id);
