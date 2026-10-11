from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "revenue_omega" / "postgresql" / "0001_revenue_omega_v1.sql"


def sql_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_revenue_omega_schema_is_isolated_and_forward_only():
    sql = sql_text().upper()
    assert "DROP TABLE" not in sql
    assert "TRUNCATE" not in sql
    assert "ALTER TABLE" not in sql
    assert "JSONB" in sql
    assert "TIMESTAMPTZ" in sql
    assert "NUMERIC(" in sql


def test_financial_tables_exist():
    sql = sql_text()
    for table in (
        "revenue_omega_agreements",
        "revenue_omega_jurisdiction_decisions",
        "revenue_omega_placements",
        "revenue_omega_compute_usage",
        "revenue_omega_billing_reservations",
        "revenue_omega_commission_calculations",
        "revenue_omega_invoice_events",
        "revenue_omega_payment_events",
        "revenue_omega_ledger_transactions",
        "revenue_omega_audit_events",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql


def test_billing_and_provider_events_have_database_uniqueness_guards():
    sql = sql_text()
    assert "billing_idempotency_key TEXT PRIMARY KEY" in sql
    assert "UNIQUE (provider, provider_event_id)" in sql
    assert "billing_idempotency_key TEXT NOT NULL UNIQUE REFERENCES revenue_omega_billing_reservations" in sql


def test_evidence_like_financial_records_are_append_only():
    sql = sql_text()
    for table in (
        "revenue_omega_jurisdiction_decisions",
        "revenue_omega_compute_usage",
        "revenue_omega_commission_calculations",
        "revenue_omega_invoice_events",
        "revenue_omega_payment_events",
        "revenue_omega_ledger_transactions",
        "revenue_omega_audit_events",
    ):
        assert f"CREATE TRIGGER {table}_no_mutation" in sql


def test_ledger_enforces_balance_in_database():
    assert "CHECK (debit_total = credit_total)" in sql_text()
