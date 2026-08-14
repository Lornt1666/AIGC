from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import EffectClass, NexusContract
from src.security.redactor import Redactor


class HierarchyRole(NexusContract):
    role_id: str = Field(pattern=r"^ROLE-[A-Z0-9-]{3,80}$")
    title: str = Field(min_length=3, max_length=120)
    corporate_role: str = Field(min_length=2, max_length=120)
    agent_cluster_id: str = Field(pattern=r"^CLUSTER-[A-Z0-9-]{3,80}$")
    mandate: str = Field(min_length=8, max_length=1000)


class DivisionSpec(NexusContract):
    division_id: str = Field(pattern=r"^DIV-[A-Z0-9-]{3,80}$")
    domain: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,80}$")
    title: str = Field(min_length=3, max_length=120)
    agent_cluster_id: str = Field(pattern=r"^CLUSTER-[A-Z0-9-]{3,80}$")


class HierarchySpec(NexusContract):
    pantheon_board: tuple[HierarchyRole, ...] = Field(min_length=1, max_length=12)
    sovereign_orchestrator: HierarchyRole
    archons: tuple[DivisionSpec, ...] = Field(min_length=1, max_length=32)
    c_suite: tuple[HierarchyRole, ...] = Field(min_length=1, max_length=32)


class FunctionCatalogItem(NexusContract):
    tool_id: str = Field(pattern=r"^TOOL-[A-Z0-9-]{3,80}$")
    function_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,120}$")
    purpose: str = Field(min_length=8, max_length=1000)
    expected_outputs: dict[str, str] = Field(default_factory=dict)
    effect_class: EffectClass


class AgentClusterSpec(NexusContract):
    cluster_id: str = Field(pattern=r"^CLUSTER-[A-Z0-9-]{3,80}$")
    agent_id: str = Field(pattern=r"^AGT-[A-Z][A-Z0-9-]{2,63}$")
    role: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,80}$")
    mandate: str = Field(min_length=8, max_length=1000)
    capabilities: tuple[str, ...] = Field(default=(), max_length=32)
    assigned_tool_ids: tuple[str, ...] = Field(default=(), max_length=16)
    depends_on_cluster_ids: tuple[str, ...] = Field(default=(), max_length=16)
    output_contract: str = Field(min_length=3, max_length=500)
    verification_function: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,120}$")


class KernelNodeSpec(NexusContract):
    node_id: str = Field(pattern=r"^KERNEL-[A-Z0-9-]{3,80}$")
    name: str = Field(min_length=3, max_length=160)
    function_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,120}$")
    depends_on_node_ids: tuple[str, ...] = Field(default=(), max_length=16)


class ConnectorSpec(NexusContract):
    connector_id: str = Field(pattern=r"^CONNECTOR-[A-Z0-9-]{3,80}$")
    protocol: Literal["REST", "GRPC", "WEBHOOK", "EVENT_BUS", "MESSAGE_QUEUE"]
    status: Literal["DESIGN_ONLY"]
    egress_enabled: Literal[False] = False


class RepositorySpec(NexusContract):
    repository_id: str = Field(pattern=r"^REPO-[A-Z0-9-]{3,80}$")
    namespace: str = Field(min_length=3, max_length=240)
    status: Literal["LOGICAL_NAMESPACE_ONLY", "IMPLEMENTED_META_REPOSITORY"]


class ExperienceProjectionSpec(NexusContract):
    projection_id: str = Field(pattern=r"^PROJECTION-[A-Z0-9-]{3,80}$")
    mode: Literal["CORPORATION", "OPERATING_SYSTEM", "CINEMATIC_UNIVERSE", "RPG_WORLD"]
    purpose: str = Field(min_length=8, max_length=500)
    boundary: str = Field(min_length=8, max_length=500)


class DeploymentComponentSpec(NexusContract):
    component_id: str = Field(pattern=r"^DEPLOY-[A-Z0-9-]{3,80}$")
    technology: str = Field(min_length=2, max_length=160)
    purpose: str = Field(min_length=8, max_length=500)
    status: Literal["DESIGN_ONLY_NOT_PROVISIONED"]


class InterfaceSpec(NexusContract):
    interface_id: str = Field(pattern=r"^API-[A-Z0-9-]{3,80}$")
    path: str = Field(pattern=r"^/[a-z][a-z0-9/_-]{1,120}$")
    maps_to: str = Field(min_length=3, max_length=300)
    status: Literal[
        "IMPLEMENTED_VERSIONED_ROUTE",
        "PLANNED_ALIAS",
        "BLOCKED_NOT_EXPOSED",
    ]
    effect_class: EffectClass


class KpiSpec(NexusContract):
    kpi_id: str = Field(pattern=r"^KPI-[A-Z0-9-]{3,80}$")
    name: str = Field(min_length=3, max_length=160)
    formula: str = Field(min_length=3, max_length=500)
    unit: str = Field(min_length=1, max_length=80)
    target_direction: Literal["MINIMIZE", "MAXIMIZE", "TARGET_RANGE"]
    status: Literal["DESIGN_ONLY"]


class ProcurementStageSpec(NexusContract):
    stage_id: str = Field(pattern=r"^PROC-[A-Z0-9-]{3,80}$")
    name: str = Field(min_length=3, max_length=160)
    output: str = Field(min_length=3, max_length=500)
    effect_ceiling: Literal["PLAN_ONLY"]


class AutodesignPolicySpec(NexusContract):
    maximum_iterations_per_run: int = Field(ge=1, le=12)
    maximum_proposals_per_iteration: int = Field(ge=1, le=6)
    maximum_parallel_agents: int = Field(ge=1, le=12)
    minimum_progress_delta: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    no_progress_limit: int = Field(ge=1, le=6)
    infinite_semantics: Literal[
        "OPEN_ENDED_SEQUENCE_OF_TERMINATING_BOUNDED_RUNS"
    ]
    self_modification_allowed: Literal[False] = False
    external_execution_allowed: Literal[False] = False


class CapabilityRoadmapItem(NexusContract):
    capability_id: str = Field(pattern=r"^CAP-[A-Z0-9-]{3,100}$")
    name: str = Field(min_length=3, max_length=200)
    priority: int = Field(ge=0, le=1000)
    depends_on: tuple[str, ...] = Field(default=(), max_length=16)
    effect_class: EffectClass
    responsible_cluster_id: str = Field(pattern=r"^CLUSTER-[A-Z0-9-]{3,80}$")
    change_targets: tuple[str, ...] = Field(min_length=1, max_length=20)
    acceptance_criteria: tuple[str, ...] = Field(min_length=1, max_length=20)


def _assert_unique(label: str, values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} IDs must be unique")


def _validate_dag(
    label: str, identifiers: list[str], dependencies: dict[str, tuple[str, ...]]
) -> None:
    known = set(identifiers)
    for identifier, required in dependencies.items():
        missing = sorted(set(required).difference(known))
        if missing:
            raise ValueError(f"{label} {identifier} has unknown dependencies: {', '.join(missing)}")
        if identifier in required:
            raise ValueError(f"{label} {identifier} cannot depend on itself")
    remaining = set(identifiers)
    resolved: set[str] = set()
    while remaining:
        ready = {
            identifier
            for identifier in remaining
            if set(dependencies[identifier]) <= resolved
        }
        if not ready:
            raise ValueError(f"{label} dependency graph contains a cycle")
        resolved.update(ready)
        remaining.difference_update(ready)


class CHCMBlueprint(NexusContract):
    schema_version: Literal["aigc.regenexcalibur-chcm.v1"]
    blueprint_id: str = Field(pattern=r"^CHCM-[A-Z0-9-]{6,100}$")
    title: str = Field(min_length=8, max_length=240)
    owner: Literal["Justice Gray Maciocha"]
    operating_mode: Literal["BOUNDED_AUTODESIGN_PLAN_ONLY"]
    invariants: tuple[str, ...] = Field(min_length=1, max_length=32)
    hierarchy: HierarchySpec
    function_catalog: tuple[FunctionCatalogItem, ...] = Field(min_length=1, max_length=16)
    agent_clusters: tuple[AgentClusterSpec, ...] = Field(min_length=1, max_length=12)
    runtime_kernel: tuple[KernelNodeSpec, ...] = Field(min_length=1, max_length=32)
    connector_fabric: tuple[ConnectorSpec, ...] = Field(min_length=1, max_length=16)
    repository_federation: tuple[RepositorySpec, ...] = Field(min_length=1, max_length=32)
    experience_projections: tuple[ExperienceProjectionSpec, ...] = Field(
        min_length=4, max_length=4
    )
    deployment_blueprint: tuple[DeploymentComponentSpec, ...] = Field(
        min_length=1, max_length=16
    )
    interface_registry: tuple[InterfaceSpec, ...] = Field(min_length=1, max_length=16)
    kpis: tuple[KpiSpec, ...] = Field(min_length=1, max_length=32)
    procurement_pipeline: tuple[ProcurementStageSpec, ...] = Field(min_length=1, max_length=16)
    autodesign_policy: AutodesignPolicySpec
    capability_roadmap: tuple[CapabilityRoadmapItem, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_blueprint_graphs(self) -> "CHCMBlueprint":
        cluster_ids = [item.cluster_id for item in self.agent_clusters]
        function_ids = [item.tool_id for item in self.function_catalog]
        node_ids = [item.node_id for item in self.runtime_kernel]
        capability_ids = [item.capability_id for item in self.capability_roadmap]
        for label, values in (
            ("agent cluster", cluster_ids),
            ("agent", [item.agent_id for item in self.agent_clusters]),
            ("function", function_ids),
            ("kernel node", node_ids),
            ("capability", capability_ids),
            ("division", [item.division_id for item in self.hierarchy.archons]),
            ("role", [item.role_id for item in (*self.hierarchy.pantheon_board, self.hierarchy.sovereign_orchestrator, *self.hierarchy.c_suite)]),
            ("connector", [item.connector_id for item in self.connector_fabric]),
            ("repository", [item.repository_id for item in self.repository_federation]),
            ("experience projection", [item.projection_id for item in self.experience_projections]),
            ("deployment component", [item.component_id for item in self.deployment_blueprint]),
            ("interface", [item.interface_id for item in self.interface_registry]),
            ("KPI", [item.kpi_id for item in self.kpis]),
            ("procurement stage", [item.stage_id for item in self.procurement_pipeline]),
        ):
            _assert_unique(label, values)
        _validate_dag(
            "agent cluster",
            cluster_ids,
            {item.cluster_id: item.depends_on_cluster_ids for item in self.agent_clusters},
        )
        _validate_dag(
            "kernel node",
            node_ids,
            {item.node_id: item.depends_on_node_ids for item in self.runtime_kernel},
        )
        _validate_dag(
            "capability",
            capability_ids,
            {item.capability_id: item.depends_on for item in self.capability_roadmap},
        )
        known_clusters = set(cluster_ids)
        known_functions = set(function_ids)
        role_cluster_refs = {
            item.agent_cluster_id
            for item in (
                *self.hierarchy.pantheon_board,
                self.hierarchy.sovereign_orchestrator,
                *self.hierarchy.c_suite,
            )
        }
        role_cluster_refs.update(item.agent_cluster_id for item in self.hierarchy.archons)
        missing_role_clusters = sorted(role_cluster_refs.difference(known_clusters))
        if missing_role_clusters:
            raise ValueError(
                "hierarchy references unknown clusters: " + ", ".join(missing_role_clusters)
            )
        for cluster in self.agent_clusters:
            missing_functions = sorted(set(cluster.assigned_tool_ids).difference(known_functions))
            if missing_functions:
                raise ValueError(
                    f"{cluster.cluster_id} references unknown functions: {', '.join(missing_functions)}"
                )
        for capability in self.capability_roadmap:
            if capability.responsible_cluster_id not in known_clusters:
                raise ValueError(
                    f"{capability.capability_id} references unknown responsible cluster"
                )
        if len(self.hierarchy.archons) != 9:
            raise ValueError("CHCM V1 requires exactly nine domain Archons")
        return self


class AutodesignState(NexusContract):
    state_id: str = Field(pattern=r"^AUTODESIGN-STATE-[A-Z0-9_-]{6,64}$")
    revision: int = Field(default=0, ge=0, le=1_000_000)
    current_capabilities: tuple[str, ...] = Field(default=(), max_length=64)
    capability_evidence: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, max_length=64
    )
    artifact_refs: tuple[str, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def unique_state_lists(self) -> "AutodesignState":
        if len(self.current_capabilities) != len(set(self.current_capabilities)):
            raise ValueError("current_capabilities must be unique")
        if len(self.artifact_refs) != len(set(self.artifact_refs)):
            raise ValueError("artifact_refs must be unique")
        if set(self.capability_evidence) != set(self.current_capabilities):
            raise ValueError(
                "capability_evidence keys must exactly match current_capabilities"
            )
        for capability_id, references in self.capability_evidence.items():
            if not references:
                raise ValueError(
                    f"capability_evidence for {capability_id} cannot be empty"
                )
            if len(references) != len(set(references)):
                raise ValueError(
                    f"capability_evidence for {capability_id} must be unique"
                )
        return self


class AutodesignIterationPolicy(NexusContract):
    current_iteration: int = Field(default=0, ge=0, le=11)
    maximum_iterations: int = Field(default=6, ge=1, le=12)
    proposal_limit: int = Field(default=3, ge=1, le=6)

    @model_validator(mode="after")
    def iteration_is_available(self) -> "AutodesignIterationPolicy":
        if self.current_iteration >= self.maximum_iterations:
            raise ValueError("current_iteration must be lower than maximum_iterations")
        return self


class AutodesignRequest(NexusContract):
    request_id: str = Field(pattern=r"^AUTODESIGN-REQ-[A-Z0-9_-]{6,64}$")
    objective: str = Field(min_length=1, max_length=4000)
    target_component: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,100}$")
    industry_scope: tuple[str, ...] = Field(min_length=1, max_length=9)
    state: AutodesignState
    iteration: AutodesignIterationPolicy = Field(default_factory=AutodesignIterationPolicy)
    execution_requested: bool = False
    deterministic_seed: Literal[42] = 42

    @model_validator(mode="after")
    def validate_request(self) -> "AutodesignRequest":
        if len(self.industry_scope) != len(set(self.industry_scope)):
            raise ValueError("industry_scope must be unique")
        payload = self.model_dump(mode="json")
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > 262_144:
            raise ValueError("autodesign request exceeds the 262144-byte contract ceiling")
        if Redactor().redact_text(serialized) != serialized:
            raise ValueError("autodesign request contains credential-like material")
        return self


class AutodesignReceipt(NexusContract):
    schema_version: Literal["aigc.regenexcalibur-autodesign-receipt.v1"]
    endpoint: Literal["POST /v1/autodesign/iterate"]
    receipt_id: str = Field(pattern=r"^AUTODESIGN-RCPT-[A-F0-9]{24}$")
    request_id: str
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    blueprint_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    hierarchy_projection: dict[str, Any]
    universalization_matrix: tuple[dict[str, Any], ...]
    gap_analysis: dict[str, Any]
    proposals: tuple[dict[str, Any], ...]
    coordination_receipt: dict[str, Any]
    evolution_continuation: dict[str, Any]
    terminal_status: Literal["PASS", "BLOCKED"]
    production_ready: Literal[False] = False
    zero_egress: Literal[True] = True
    self_modification_performed: Literal[False] = False
    state_transition_applied: Literal[False] = False
    provider_calls_performed: Literal[0] = 0
    tool_dispatches_performed: Literal[0] = 0
    processes_spawned: Literal[0] = 0
    memory_writes_performed: Literal[0] = 0
    external_actions_performed: Literal[0] = 0
    authority_granted: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AutodesignCampaignReceipt(NexusContract):
    schema_version: Literal["aigc.regenexcalibur-autodesign-shadow-campaign.v1"]
    campaign_id: str = Field(pattern=r"^AUTODESIGN-CAMPAIGN-[A-F0-9]{24}$")
    initial_request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    iteration_receipts: tuple[dict[str, Any], ...]
    initial_capabilities: tuple[str, ...]
    shadow_capabilities: tuple[str, ...]
    newly_proposed_capabilities: tuple[str, ...]
    remaining_capabilities: tuple[str, ...]
    first_blocker: str | None
    terminal_status: Literal["PASS", "BLOCKED"]
    production_ready: Literal[False] = False
    zero_egress: Literal[True] = True
    shadow_only: Literal[True] = True
    self_modification_performed: Literal[False] = False
    state_transition_applied: Literal[False] = False
    provider_calls_performed: Literal[0] = 0
    tool_dispatches_performed: Literal[0] = 0
    processes_spawned: Literal[0] = 0
    memory_writes_performed: Literal[0] = 0
    external_actions_performed: Literal[0] = 0
    authority_granted: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
