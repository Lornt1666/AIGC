from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Any, Mapping


def canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class EvidenceReceipt:
    receipt_id: str
    event_type: str
    repository_sha: str
    repository_tree_sha: str
    schema_version: str
    payload_digest: str
    previous_receipt_digest: str
    created_at: str
    authority: Mapping[str, bool]
    receipt_digest: str = ""

    @classmethod
    def compile(
        cls,
        *,
        receipt_id: str,
        event_type: str,
        repository_sha: str,
        repository_tree_sha: str,
        schema_version: str,
        payload_digest: str,
        previous_receipt_digest: str = "0" * 64,
        created_at: str | None = None,
    ) -> "EvidenceReceipt":
        authority = {
            "production_activation": False,
            "public_access": False,
            "live_model_call": False,
            "financial_action": False,
            "automatic_merge": False,
        }
        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        body = {
            "receipt_id": receipt_id,
            "event_type": event_type,
            "repository_sha": repository_sha,
            "repository_tree_sha": repository_tree_sha,
            "schema_version": schema_version,
            "payload_digest": payload_digest,
            "previous_receipt_digest": previous_receipt_digest,
            "created_at": timestamp,
            "authority": authority,
        }
        receipt = cls(**body, receipt_digest=canonical_digest(body))
        receipt.verify()
        return receipt

    def verify(self) -> None:
        values = (
            self.payload_digest,
            self.previous_receipt_digest,
            self.receipt_digest,
        )
        if any(len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value) for value in values):
            raise ValueError("evidence digests must be lowercase SHA-256 values")
        if len(self.repository_sha) != 40 or len(self.repository_tree_sha) != 40:
            raise ValueError("evidence must bind exact commit and tree SHAs")
        if any(self.authority.values()):
            raise PermissionError("evidence receipt cannot grant authority")
        body = {
            "receipt_id": self.receipt_id,
            "event_type": self.event_type,
            "repository_sha": self.repository_sha,
            "repository_tree_sha": self.repository_tree_sha,
            "schema_version": self.schema_version,
            "payload_digest": self.payload_digest,
            "previous_receipt_digest": self.previous_receipt_digest,
            "created_at": self.created_at,
            "authority": dict(self.authority),
        }
        if not hmac.compare_digest(self.receipt_digest, canonical_digest(body)):
            raise PermissionError("evidence receipt integrity failed")

    def tampered(self, **changes: Any) -> "EvidenceReceipt":
        return replace(self, **changes)
