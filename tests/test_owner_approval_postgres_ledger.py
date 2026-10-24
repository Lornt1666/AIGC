from __future__ import annotations

from src.core.verified_owner_approval import PostgresApprovalReplayLedger


class Context:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.sql = ""
        self.params = None
        self.tx = Context(None)

    def transaction(self):
        return self.tx

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return ContextResult(self.row)


class ContextResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakePool:
    def __init__(self, connection):
        self._connection = connection

    def connection(self):
        return Context(self._connection)


def test_postgres_replay_ledger_uses_atomic_insert_and_returns_true_on_first_use():
    conn = FakeConnection(("approval-1",))
    ledger = PostgresApprovalReplayLedger(FakePool(conn))
    assert ledger.consume_once(
        approval_id="approval-1",
        nonce="nonce-1",
        payload_sha256="a" * 64,
    ) is True
    assert "ON CONFLICT DO NOTHING" in conn.sql
    assert "RETURNING approval_id" in conn.sql
    assert conn.params == ("approval-1", "nonce-1", "a" * 64)


def test_postgres_replay_ledger_returns_false_for_replay_or_conflict():
    conn = FakeConnection(None)
    ledger = PostgresApprovalReplayLedger(FakePool(conn))
    assert ledger.consume_once(
        approval_id="approval-1",
        nonce="nonce-1",
        payload_sha256="a" * 64,
    ) is False
