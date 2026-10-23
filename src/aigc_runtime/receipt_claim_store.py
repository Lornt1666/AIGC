"""PostgreSQL-backed receipt replay/collision ledger for RX-148.

Evidence receipts may be re-observed only when receipt ID, signed payload digest,
purpose, issuer and candidate binding are identical. One-time authorization purposes
are rejected on second use. The database role must be independently provisioned.
"""
from __future__ import annotations

import os
import re
from typing import Any, Mapping

import psycopg


class ReceiptClaimError(ValueError):
    pass


_SINGLE_USE_PURPOSES = {"tool-permit", "irreversible-action-approval", "transaction-authorization"}


class PostgresReceiptClaimStore:
    def __init__(self, database_url: str | None = None, *, timeout_seconds: float = 5.0):
        self.database_url = database_url or os.environ.get("AIGC_REPLAY_DATABASE_URL", "")
        if not self.database_url:
            raise ReceiptClaimError("persistent_receipt_store_required")
        self.timeout_seconds = timeout_seconds

    def claim(self, payload: Mapping[str, Any], verification: Mapping[str, Any]) -> dict[str, Any]:
        receipt_id = verification.get("receipt_id")
        digest = verification.get("payload_digest")
        purpose = verification.get("purpose")
        issuer = verification.get("issuer")
        candidate = payload.get("candidate_sha")
        if not isinstance(receipt_id, str) or not receipt_id:
            raise ReceiptClaimError("receipt_id_missing")
        if not isinstance(digest, str):
            raise ReceiptClaimError("verified_payload_digest_missing")
        digest = digest.removeprefix("sha256:")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ReceiptClaimError("verified_payload_digest_invalid")
        if not isinstance(purpose, str) or not isinstance(issuer, str):
            raise ReceiptClaimError("receipt_purpose_or_issuer_missing")
        if candidate is not None and (not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{40}", candidate)):
            raise ReceiptClaimError("receipt_candidate_sha_invalid")
        try:
            with psycopg.connect(self.database_url, connect_timeout=max(1, int(self.timeout_seconds))) as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO aigc_receipt_claims
                               (receipt_id,payload_sha256,purpose,issuer,candidate_sha)
                               VALUES(%s,%s,%s,%s,%s)
                               ON CONFLICT(receipt_id) DO NOTHING
                               RETURNING receipt_id""",
                            (receipt_id, digest, purpose, issuer, candidate))
                        inserted = cur.fetchone()
                        if inserted:
                            return {"status": "FIRST_OBSERVATION", "receipt_id": receipt_id}
                        cur.execute(
                            """SELECT payload_sha256,purpose,issuer,candidate_sha,observation_count
                               FROM aigc_receipt_claims WHERE receipt_id=%s FOR UPDATE""", (receipt_id,))
                        row = cur.fetchone()
                        if not row:
                            raise ReceiptClaimError("receipt_claim_conflict_without_row")
                        existing_digest, existing_purpose, existing_issuer, existing_candidate, count = row
                        if (existing_digest.strip() != digest or existing_purpose != purpose
                                or existing_issuer != issuer or existing_candidate != candidate):
                            raise ReceiptClaimError("receipt_id_reused_with_different_claims")
                        if purpose in _SINGLE_USE_PURPOSES and int(count) >= 1:
                            raise ReceiptClaimError("single_use_receipt_replayed")
                        cur.execute(
                            "UPDATE aigc_receipt_claims SET last_seen_at=now(),observation_count=observation_count+1 WHERE receipt_id=%s",
                            (receipt_id,))
                        return {"status": "SAME_EVIDENCE_REOBSERVED", "receipt_id": receipt_id}
        except ReceiptClaimError:
            raise
        except psycopg.Error as exc:
            raise ReceiptClaimError("persistent_receipt_store_unavailable:" + type(exc).__name__) from exc
