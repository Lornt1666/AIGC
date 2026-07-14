from __future__ import annotations

import json
import sqlite3

from src.domain.identity import (
    IdentityEvidenceReceipt,
    IdentityReplayConflict,
)

from .connection import SQLiteConnectionFactory


def _canonical(value: dict[str, object]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _from_row(row: sqlite3.Row) -> IdentityEvidenceReceipt:
    return IdentityEvidenceReceipt.from_dict(json.loads(row["receipt_json"]))


class SQLiteIdentityEvidenceReceiptRepository:
    """Append-only PIBC-v1 receipt repository."""

    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self.factory = factory

    def append(
        self,
        receipt: IdentityEvidenceReceipt,
    ) -> IdentityEvidenceReceipt:
        payload = receipt.to_dict()
        payload_json = _canonical(payload)
        with self.factory.transaction() as connection:
            by_id = connection.execute(
                """
                SELECT * FROM identity_evidence_receipts
                WHERE receipt_id = ?
                """,
                (receipt.receipt_id,),
            ).fetchone()
            if by_id:
                if by_id["receipt_json"] != payload_json:
                    raise ValueError("Identity evidence receipt is immutable")
                return _from_row(by_id)

            by_replay = connection.execute(
                """
                SELECT * FROM identity_evidence_receipts
                WHERE replay_key_digest = ?
                """,
                (receipt.replay_key_digest,),
            ).fetchone()
            if by_replay:
                if by_replay["request_digest"] != receipt.request_digest:
                    raise IdentityReplayConflict(
                        "Identity assertion replayed with different intent"
                    )
                return _from_row(by_replay)

            connection.execute(
                """
                INSERT INTO identity_evidence_receipts(
                    receipt_id,
                    request_digest,
                    replay_key_digest,
                    result,
                    reason_codes_json,
                    provider_class,
                    provider_binding_id,
                    assertion_id,
                    principal_id,
                    membership_id,
                    session_id,
                    tenant_id,
                    project_id,
                    exact_revision,
                    receipt_json,
                    created_at,
                    expires_at,
                    retention_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.receipt_id,
                    receipt.request_digest,
                    receipt.replay_key_digest,
                    receipt.result.value,
                    json.dumps(
                        [item.value for item in receipt.reason_codes],
                        sort_keys=True,
                    ),
                    (
                        receipt.provider_class.value
                        if receipt.provider_class
                        else None
                    ),
                    receipt.provider_binding_id,
                    receipt.assertion_id,
                    receipt.principal_id,
                    receipt.membership_id,
                    receipt.session_id,
                    receipt.tenant_id,
                    receipt.project_id,
                    receipt.exact_revision,
                    payload_json,
                    payload["created_at"],
                    payload["expires_at"],
                    receipt.retention_class,
                ),
            )
            return receipt

    def get(
        self,
        receipt_id: str,
    ) -> IdentityEvidenceReceipt | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM identity_evidence_receipts
                WHERE receipt_id = ?
                """,
                (receipt_id,),
            ).fetchone()
        return _from_row(row) if row else None

    def get_by_replay_key(
        self,
        replay_key_digest: str,
    ) -> IdentityEvidenceReceipt | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM identity_evidence_receipts
                WHERE replay_key_digest = ?
                """,
                (replay_key_digest,),
            ).fetchone()
        return _from_row(row) if row else None
