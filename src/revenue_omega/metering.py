from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import ComputeUsageEvent, canonical_sha256, money


@dataclass(frozen=True)
class MeteringReport:
    placement_id: str
    currency: str
    usage_count: int
    total_direct_cost: Decimal
    providers: tuple[str, ...]
    resource_types: tuple[str, ...]
    usage_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    report_hash: str


def build_metering_report(
    events: Iterable[ComputeUsageEvent],
    *,
    placement_id: str,
    currency: str,
) -> MeteringReport:
    values = tuple(events)
    seen: set[str] = set()
    evidence: set[str] = set()
    providers: set[str] = set()
    resources: set[str] = set()

    for event in values:
        if not event.usage_id:
            raise ValueError("usage event ID is required")
        if event.usage_id in seen:
            raise ValueError(f"duplicate usage event: {event.usage_id}")
        seen.add(event.usage_id)
        if event.placement_id != placement_id:
            raise ValueError("usage event placement mismatch")
        if event.currency != currency:
            raise ValueError("usage event currency mismatch")
        if not event.evidence_ref:
            raise ValueError("billable compute usage requires evidence")
        evidence.add(event.evidence_ref)
        providers.add(event.provider)
        resources.add(event.resource_type)

    total = money(sum((event.actual_cost for event in values), Decimal("0")))
    payload = {
        "placement_id": placement_id,
        "currency": currency,
        "usage_count": len(values),
        "total_direct_cost": total,
        "providers": sorted(providers),
        "resource_types": sorted(resources),
        "usage_ids": sorted(seen),
        "evidence_refs": sorted(evidence),
    }
    return MeteringReport(
        placement_id=placement_id,
        currency=currency,
        usage_count=len(values),
        total_direct_cost=total,
        providers=tuple(sorted(providers)),
        resource_types=tuple(sorted(resources)),
        usage_ids=tuple(sorted(seen)),
        evidence_refs=tuple(sorted(evidence)),
        report_hash=canonical_sha256(payload),
    )
