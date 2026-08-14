from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.epistemic.models import ArtifactState
from src.domain.nexus.contracts import ContextEnvelope, WorkOrder
from src.domain.nexus.evidence import EvidenceReference
from src.domain.nexus.memory import MemoryRecord


@dataclass(frozen=True)
class ContextProjectionPolicy:
    maximum_memories: int = 12
    maximum_evidence_refs: int = 24
    allowed_sensitivities: tuple[str, ...] = ("PUBLIC", "INTERNAL")


def _terms(work_order: WorkOrder) -> set[str]:
    tokens = set(work_order.objective.lower().replace("/", " ").replace("-", " ").split())
    tokens.update(tag.lower() for tag in work_order.domain_tags)
    return {token.strip(".,:;()[]{}") for token in tokens if len(token) >= 3}


def build_context_envelope(
    *,
    work_order: WorkOrder,
    state: ArtifactState,
    memories: tuple[MemoryRecord, ...],
    evidence: tuple[EvidenceReference, ...],
    authoritative_now: datetime,
    policy: ContextProjectionPolicy = ContextProjectionPolicy(),
) -> ContextEnvelope:
    if policy.maximum_memories < 0 or policy.maximum_evidence_refs < 0:
        raise ValueError("context projection limits cannot be negative")

    terms = _terms(work_order)
    active = [
        item
        for item in memories
        if item.is_eligible_at(authoritative_now=authoritative_now)
        and item.sensitivity in policy.allowed_sensitivities
    ]

    def score(item: MemoryRecord) -> tuple[int, float, str]:
        normalized = item.content.lower()
        matches = sum(1 for term in terms if term in normalized)
        return (-matches, -item.valid_from.timestamp(), item.memory_id)

    ranked = sorted(active, key=score)
    selected = tuple(ranked[: policy.maximum_memories])

    evidence_by_id = {item.evidence_id: item for item in evidence}
    requested_refs = []
    for memory in selected:
        requested_refs.extend(memory.evidence_bindings)

    unique_refs = []
    seen = set()
    if policy.maximum_evidence_refs > 0:
        for ref in requested_refs:
            if ref in seen:
                continue
            if ref not in evidence_by_id:
                raise ValueError(f"memory evidence reference does not resolve: {ref}")
            seen.add(ref)
            unique_refs.append(ref)
            if len(unique_refs) >= policy.maximum_evidence_refs:
                break

    payload = {
        "work_order_id": work_order.work_order_id,
        "state_hash": canonical_sha256(state),
        "memory_refs": [item.memory_id for item in selected],
        "evidence_refs": unique_refs,
    }
    context_id = "CTX-" + canonical_sha256(payload)[:24].upper()

    return ContextEnvelope(
        context_id=context_id,
        work_order_id=work_order.work_order_id,
        state_hash=payload["state_hash"],
        relevant_claim_ids=tuple(claim.id for claim in state.claims),
        evidence_refs=tuple(unique_refs),
        memory_refs=tuple(item.memory_id for item in selected),
    )
