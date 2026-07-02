from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


class ApprovalTokenError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovalTokenRecord:
    token_id: str
    token_hash: str
    created_at: str
    expires_at: str
    scope: str
    phase: str
    reason: str
    one_time: bool = True
    used_at: str = ""
    revoked: bool = False


@dataclass(frozen=True)
class IssuedApprovalToken:
    token: str
    record: ApprovalTokenRecord


class ApprovalTokenStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def issue_token(
        self,
        scope: str,
        phase: str,
        reason: str,
        ttl_minutes: int = 30,
        one_time: bool = True,
    ) -> IssuedApprovalToken:
        raw_token = "AIGC-APPROVAL-" + secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        record = ApprovalTokenRecord(
            token_id=f"AIGC-APPROVAL-TOKEN-{uuid.uuid4()}",
            token_hash=hash_token(raw_token),
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=ttl_minutes)).isoformat(),
            scope=scope,
            phase=phase,
            reason=reason,
            one_time=one_time,
        )
        self._append(record)
        return IssuedApprovalToken(token=raw_token, record=record)

    def validate_token(self, token: str, required_scope: str, phase: str, mark_used: bool = True) -> ApprovalTokenRecord:
        token_hash = hash_token(token)
        records = self._read_records()
        for index in range(len(records) - 1, -1, -1):
            record = records[index]
            if record.token_hash != token_hash:
                continue
            if record.revoked:
                raise ApprovalTokenError("Approval token was revoked.")
            if record.scope != required_scope:
                raise ApprovalTokenError("Approval token scope mismatch.")
            if record.phase != phase:
                raise ApprovalTokenError("Approval token phase mismatch.")
            if record.used_at and record.one_time:
                raise ApprovalTokenError("Approval token has already been used.")
            expires_at = datetime.fromisoformat(record.expires_at)
            if datetime.now(timezone.utc) > expires_at:
                raise ApprovalTokenError("Approval token expired.")
            if mark_used and record.one_time:
                updated = ApprovalTokenRecord(
                    **{
                        **asdict(record),
                        "used_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                records[index] = updated
                self._write_records(records)
                return updated
            return record
        raise ApprovalTokenError("Approval token not found.")

    def _append(self, record: ApprovalTokenRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def _read_records(self) -> List[ApprovalTokenRecord]:
        if not self.path.exists():
            return []
        records: List[ApprovalTokenRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload: Dict[str, Any] = json.loads(line)
                records.append(ApprovalTokenRecord(**payload))
        return records

    def _write_records(self, records: List[ApprovalTokenRecord]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
