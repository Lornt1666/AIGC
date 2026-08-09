from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

from .models import canonical_sha256, money


PROHIBITED_METADATA_KEYS = {
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "private_key",
    "card_number",
    "cvv",
}


@dataclass(frozen=True)
class RevenueTelemetryEvent:
    event_id: str
    event_type: str
    task_id: str
    placement_id: str
    invoice_id: str
    provider: str
    duration_ms: int
    direct_cost: Decimal
    currency: str
    status: str
    evidence_ref: str
    metadata: Mapping[str, str]
    event_hash: str

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        event_type: str,
        task_id: str,
        placement_id: str = "",
        invoice_id: str = "",
        provider: str = "",
        duration_ms: int = 0,
        direct_cost: Decimal | str | int = Decimal("0"),
        currency: str = "CAD",
        status: str,
        evidence_ref: str,
        metadata: Mapping[str, str] | None = None,
    ) -> "RevenueTelemetryEvent":
        if not event_id or not event_type or not task_id or not status:
            raise ValueError("telemetry identity/type/task/status are required")
        if duration_ms < 0:
            raise ValueError("telemetry duration cannot be negative")
        normalized_cost = money(direct_cost)
        if normalized_cost < Decimal("0"):
            raise ValueError("telemetry direct cost cannot be negative")
        if not evidence_ref:
            raise ValueError("telemetry event requires an evidence reference")
        clean_metadata = dict(metadata or {})
        for key in clean_metadata:
            normalized = key.lower().replace("-", "_")
            if normalized in PROHIBITED_METADATA_KEYS or any(
                marker in normalized for marker in ("password", "secret", "private_key", "api_key", "authorization")
            ):
                raise ValueError(f"prohibited telemetry metadata key: {key}")
        payload = {
            "event_id": event_id,
            "event_type": event_type,
            "task_id": task_id,
            "placement_id": placement_id,
            "invoice_id": invoice_id,
            "provider": provider,
            "duration_ms": duration_ms,
            "direct_cost": normalized_cost,
            "currency": currency,
            "status": status,
            "evidence_ref": evidence_ref,
            "metadata": clean_metadata,
        }
        return cls(event_hash=canonical_sha256(payload), **payload)


@dataclass(frozen=True)
class RevenueTelemetrySummary:
    event_count: int
    total_duration_ms: int
    total_direct_cost: Decimal
    event_types: tuple[str, ...]
    providers: tuple[str, ...]
    statuses: tuple[str, ...]
    summary_hash: str


def summarize_telemetry(events: Iterable[RevenueTelemetryEvent], *, currency: str) -> RevenueTelemetrySummary:
    values = tuple(events)
    ids: set[str] = set()
    for item in values:
        if item.event_id in ids:
            raise ValueError(f"duplicate telemetry event: {item.event_id}")
        ids.add(item.event_id)
        if item.currency != currency:
            raise ValueError("telemetry currency mismatch")

    total_duration = sum(item.duration_ms for item in values)
    total_cost = money(sum((item.direct_cost for item in values), Decimal("0")))
    payload = {
        "event_ids": sorted(ids),
        "currency": currency,
        "event_count": len(values),
        "total_duration_ms": total_duration,
        "total_direct_cost": total_cost,
        "event_types": sorted({item.event_type for item in values}),
        "providers": sorted({item.provider for item in values if item.provider}),
        "statuses": sorted({item.status for item in values}),
    }
    return RevenueTelemetrySummary(
        event_count=len(values),
        total_duration_ms=total_duration,
        total_direct_cost=total_cost,
        event_types=tuple(payload["event_types"]),
        providers=tuple(payload["providers"]),
        statuses=tuple(payload["statuses"]),
        summary_hash=canonical_sha256(payload),
    )
