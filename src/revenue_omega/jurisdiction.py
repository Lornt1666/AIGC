from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Mapping, Protocol

from .models import canonical_sha256


def _parse_utc(value: str) -> datetime:
    if not value:
        raise ValueError("timestamp is required")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class JurisdictionDecision:
    decision_id: str
    jurisdiction: str
    service_type: str
    payer_model: str
    allowed: bool
    conditions: tuple[str, ...]
    reviewed_by: str
    reviewed_at: str
    expires_at: str
    source_refs: tuple[str, ...]
    decision_hash: str

    @classmethod
    def create(
        cls,
        *,
        decision_id: str,
        jurisdiction: str,
        service_type: str,
        payer_model: str,
        allowed: bool,
        conditions: tuple[str, ...],
        reviewed_by: str,
        reviewed_at: str,
        expires_at: str,
        source_refs: tuple[str, ...],
    ) -> "JurisdictionDecision":
        payload = {
            "decision_id": decision_id,
            "jurisdiction": jurisdiction,
            "service_type": service_type,
            "payer_model": payer_model,
            "allowed": allowed,
            "conditions": conditions,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "expires_at": expires_at,
            "source_refs": source_refs,
        }
        return cls(decision_hash=canonical_sha256(payload), **payload)

    def verify_integrity(self) -> bool:
        payload = asdict(self)
        supplied_hash = payload.pop("decision_hash")
        return canonical_sha256(payload) == supplied_hash

    def is_current(self, *, now: datetime | None = None) -> bool:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        reviewed = _parse_utc(self.reviewed_at)
        expires = _parse_utc(self.expires_at)
        return reviewed <= current < expires


class JurisdictionDecisionRepository(Protocol):
    """Read-only persistent decision repository.

    Production implementations must resolve an immutable persisted decision by
    ID. A caller-supplied boolean or unattested decision object is insufficient.
    """

    def get(self, decision_id: str) -> JurisdictionDecision | None: ...


class MappingJurisdictionDecisionRepository:
    """Deterministic repository for tests, fixtures, and read-only snapshots."""

    def __init__(self, decisions: Mapping[str, JurisdictionDecision]):
        self._decisions = dict(decisions)

    def get(self, decision_id: str) -> JurisdictionDecision | None:
        return self._decisions.get(decision_id)
