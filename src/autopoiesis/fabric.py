from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .contracts import EffectClass, StrictContract, canonical_sha256, stable_id


class AdapterKind(StrEnum):
    MODEL = "MODEL"
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"
    ORCHESTRATION = "ORCHESTRATION"
    MODALITY = "MODALITY"
    TOOL = "TOOL"


class AdapterStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    QUARANTINED = "QUARANTINED"


class AdapterManifest(StrictContract):
    """Provider-neutral capability declaration for one replaceable adapter."""

    adapter_id: str = Field(pattern=r"^ADAPTER-[A-Z0-9_-]{4,96}$")
    kind: AdapterKind
    protocol: str = Field(min_length=2, max_length=120)
    implementation_version: str = Field(min_length=1, max_length=120)
    capabilities: tuple[str, ...] = Field(min_length=1, max_length=128)
    supported_effects: tuple[EffectClass, ...] = Field(min_length=1, max_length=16)
    hardware_targets: tuple[str, ...] = Field(default=(), max_length=32)
    data_locality: Literal["LOCAL_ONLY", "LOCAL_OR_REMOTE", "REMOTE_ONLY"]
    open_standard: bool
    proprietary_dependency: bool
    status: AdapterStatus = AdapterStatus.HEALTHY
    quality_score: float = Field(ge=0.0, le=1.0)
    portability_score: float = Field(ge=0.0, le=1.0)
    estimated_latency_ms: float = Field(ge=0.0)
    estimated_cost_units: float = Field(ge=0.0)
    health_score: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def normalize_manifest_sets(self) -> "AdapterManifest":
        for label, values in (
            ("capabilities", self.capabilities),
            ("supported_effects", self.supported_effects),
            ("hardware_targets", self.hardware_targets),
            ("evidence_refs", self.evidence_refs),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"adapter {label} must be unique")
        if self.data_locality == "LOCAL_ONLY" and self.proprietary_dependency:
            # A proprietary local binary may be useful, but it cannot be the
            # sole reference path in a sovereign local-only profile.
            if self.portability_score >= 1.0:
                raise ValueError(
                    "proprietary local-only adapter cannot claim perfect portability"
                )
        return self

    @property
    def digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"digest"}))


class WorkloadDemand(StrictContract):
    workload_id: str = Field(pattern=r"^WORKLOAD-[A-Z0-9_-]{4,96}$")
    kind: AdapterKind
    required_capabilities: tuple[str, ...] = Field(min_length=1, max_length=128)
    required_effect: EffectClass
    allowed_hardware_targets: tuple[str, ...] = Field(default=(), max_length=32)
    local_only: bool = True
    open_standard_required: bool = True
    proprietary_dependency_allowed: bool = False
    maximum_latency_ms: float | None = Field(default=None, gt=0.0)
    maximum_cost_units: float | None = Field(default=None, ge=0.0)
    minimum_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    minimum_portability: float = Field(default=0.0, ge=0.0, le=1.0)
    minimum_health: float = Field(default=0.0, ge=0.0, le=1.0)


class RoutingWeights(StrictContract):
    quality: float = Field(default=3.0, ge=0.0)
    portability: float = Field(default=3.0, ge=0.0)
    health: float = Field(default=2.0, ge=0.0)
    latency: float = Field(default=1.0, ge=0.0)
    cost: float = Field(default=1.0, ge=0.0)
    open_standard_bonus: float = Field(default=0.25, ge=0.0)
    local_bonus: float = Field(default=0.25, ge=0.0)

    @model_validator(mode="after")
    def positive_total(self) -> "RoutingWeights":
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("routing weights must have a positive total")
        return self


class AdapterRejection(StrictContract):
    adapter_id: str
    reasons: tuple[str, ...] = Field(min_length=1, max_length=32)


class RoutingDecision(StrictContract):
    decision_id: str = Field(pattern=r"^ROUTE-[A-Z0-9_-]{6,96}$")
    workload_id: str
    selected_adapter_id: str | None
    eligible_adapter_ids: tuple[str, ...]
    rejected: tuple[AdapterRejection, ...]
    score_by_adapter: dict[str, float]
    terminal_status: Literal["SELECTED", "NO_ADMISSIBLE_ADAPTER"]
    deterministic: Literal[True] = True
    vendor_identity_used_as_score: Literal[False] = False

    @property
    def digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"digest"}))


class FabricRegistry(StrictContract):
    schema_version: Literal["aigc.adapter-fabric.v1"] = "aigc.adapter-fabric.v1"
    registry_id: str = Field(pattern=r"^FABRIC-[A-Z0-9_-]{4,96}$")
    revision: int = Field(ge=1)
    adapters: tuple[AdapterManifest, ...] = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def unique_adapters(self) -> "FabricRegistry":
        identifiers = [item.adapter_id for item in self.adapters]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("adapter IDs must be unique")
        return self

    @property
    def digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"digest"}))


def _rejection_reasons(adapter: AdapterManifest, demand: WorkloadDemand) -> tuple[str, ...]:
    reasons: list[str] = []
    if adapter.kind != demand.kind:
        reasons.append("KIND_MISMATCH")
    missing = sorted(set(demand.required_capabilities).difference(adapter.capabilities))
    if missing:
        reasons.append("MISSING_CAPABILITIES:" + ",".join(missing))
    if demand.required_effect not in adapter.supported_effects:
        reasons.append("EFFECT_UNSUPPORTED")
    if adapter.status in {AdapterStatus.UNAVAILABLE, AdapterStatus.QUARANTINED}:
        reasons.append("ADAPTER_NOT_AVAILABLE")
    if demand.local_only and adapter.data_locality == "REMOTE_ONLY":
        reasons.append("LOCALITY_VIOLATION")
    if demand.open_standard_required and not adapter.open_standard:
        reasons.append("OPEN_STANDARD_REQUIRED")
    if not demand.proprietary_dependency_allowed and adapter.proprietary_dependency:
        reasons.append("PROPRIETARY_DEPENDENCY_DENIED")
    if demand.allowed_hardware_targets and not set(adapter.hardware_targets).intersection(
        demand.allowed_hardware_targets
    ):
        reasons.append("HARDWARE_TARGET_MISMATCH")
    if demand.maximum_latency_ms is not None and adapter.estimated_latency_ms > demand.maximum_latency_ms:
        reasons.append("LATENCY_CEILING_EXCEEDED")
    if demand.maximum_cost_units is not None and adapter.estimated_cost_units > demand.maximum_cost_units:
        reasons.append("COST_CEILING_EXCEEDED")
    if adapter.quality_score < demand.minimum_quality:
        reasons.append("QUALITY_FLOOR_NOT_MET")
    if adapter.portability_score < demand.minimum_portability:
        reasons.append("PORTABILITY_FLOOR_NOT_MET")
    if adapter.health_score < demand.minimum_health:
        reasons.append("HEALTH_FLOOR_NOT_MET")
    return tuple(reasons)


def _routing_score(
    adapter: AdapterManifest,
    demand: WorkloadDemand,
    weights: RoutingWeights,
) -> float:
    latency_reference = demand.maximum_latency_ms or max(adapter.estimated_latency_ms, 1.0)
    cost_reference = demand.maximum_cost_units
    if cost_reference is None:
        cost_reference = max(adapter.estimated_cost_units, 1.0)
    latency_component = 1.0 - min(adapter.estimated_latency_ms / latency_reference, 1.0)
    cost_component = 1.0 - min(adapter.estimated_cost_units / max(cost_reference, 1e-12), 1.0)
    score = (
        adapter.quality_score * weights.quality
        + adapter.portability_score * weights.portability
        + adapter.health_score * weights.health
        + latency_component * weights.latency
        + cost_component * weights.cost
        + (weights.open_standard_bonus if adapter.open_standard else 0.0)
        + (weights.local_bonus if adapter.data_locality == "LOCAL_ONLY" else 0.0)
    )
    return round(score, 12)


def select_adapter(
    registry: FabricRegistry,
    demand: WorkloadDemand,
    *,
    weights: RoutingWeights | None = None,
) -> RoutingDecision:
    """Select the best admissible adapter without scoring vendor identity.

    Hard policy and capability gates are evaluated before optimization.  The
    deterministic adapter ID tie-breaker makes replay reproducible.
    """

    weights = weights or RoutingWeights()
    rejected: list[AdapterRejection] = []
    scores: dict[str, float] = {}
    eligible: list[AdapterManifest] = []
    for adapter in sorted(registry.adapters, key=lambda item: item.adapter_id):
        reasons = _rejection_reasons(adapter, demand)
        if reasons:
            rejected.append(AdapterRejection(adapter_id=adapter.adapter_id, reasons=reasons))
            continue
        eligible.append(adapter)
        scores[adapter.adapter_id] = _routing_score(adapter, demand, weights)

    selected = None
    if eligible:
        selected = sorted(
            eligible,
            key=lambda item: (-scores[item.adapter_id], item.adapter_id),
        )[0]

    seed = {
        "registry_sha256": registry.digest,
        "demand": demand.model_dump(mode="json"),
        "weights": weights.model_dump(mode="json"),
        "eligible": [item.adapter_id for item in eligible],
        "rejected": [item.model_dump(mode="json") for item in rejected],
        "scores": scores,
        "selected": selected.adapter_id if selected else None,
    }
    return RoutingDecision(
        decision_id=stable_id("ROUTE", seed),
        workload_id=demand.workload_id,
        selected_adapter_id=selected.adapter_id if selected else None,
        eligible_adapter_ids=tuple(item.adapter_id for item in eligible),
        rejected=tuple(rejected),
        score_by_adapter=scores,
        terminal_status="SELECTED" if selected else "NO_ADMISSIBLE_ADAPTER",
    )


def load_fabric_registry(path: str | Path) -> FabricRegistry:
    return FabricRegistry.model_validate_json(Path(path).read_text(encoding="utf-8"))
