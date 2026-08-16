from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class StrictContract(BaseModel):
    """Closed, immutable contract used by the local autopoietic control spine."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        str_strip_whitespace=True,
    )


def _jsonable(value: Any) -> Any:
    """Recursively normalize contract values before canonical JSON hashing.

    Receipt seeds are intentionally assembled before final Pydantic validation, so
    they may contain nested BaseModel instances.  Canonical hashing must therefore
    normalize the entire object graph rather than only the root value.
    """

    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="json", exclude_none=False))
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_jsonable(item) for item in value), key=repr)
    return value


def canonical_json_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    payload = _jsonable(value)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: BaseModel | dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def stable_id(prefix: str, value: BaseModel | dict[str, Any], length: int = 24) -> str:
    return f"{prefix}-{canonical_sha256(value)[:length].upper()}"


class EffectClass(StrEnum):
    PURE = "PURE"
    READ_LOCAL = "READ_LOCAL"
    READ_EXTERNAL = "READ_EXTERNAL"
    WRITE_REVERSIBLE = "WRITE_REVERSIBLE"
    WRITE_COMPENSATABLE = "WRITE_COMPENSATABLE"
    WRITE_IRREVERSIBLE = "WRITE_IRREVERSIBLE"
    FINANCIAL = "FINANCIAL"
    COMMUNICATION = "COMMUNICATION"
    DEPLOYMENT = "DEPLOYMENT"
    SECURITY_SENSITIVE = "SECURITY_SENSITIVE"


EFFECT_ORDER: tuple[EffectClass, ...] = (
    EffectClass.PURE,
    EffectClass.READ_LOCAL,
    EffectClass.READ_EXTERNAL,
    EffectClass.WRITE_REVERSIBLE,
    EffectClass.WRITE_COMPENSATABLE,
    EffectClass.WRITE_IRREVERSIBLE,
    EffectClass.SECURITY_SENSITIVE,
    EffectClass.COMMUNICATION,
    EffectClass.DEPLOYMENT,
    EffectClass.FINANCIAL,
)


def effect_rank(effect: EffectClass) -> int:
    return EFFECT_ORDER.index(effect)


class CyclePhase(StrEnum):
    CREATED = "CREATED"
    SENSED = "SENSED"
    FORMULATED = "FORMULATED"
    SYNTHESIZED = "SYNTHESIZED"
    VERIFIED = "VERIFIED"
    AWAITING_OPERATOR = "AWAITING_OPERATOR"
    INSTANTIATED_SHADOW = "INSTANTIATED_SHADOW"
    PROMOTED_SHADOW = "PROMOTED_SHADOW"
    ROLLED_BACK = "ROLLED_BACK"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    NO_CHANGE_REQUIRED = "NO_CHANGE_REQUIRED"


class GateResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


class DeficitClass(StrEnum):
    QUALITY = "QUALITY"
    THROUGHPUT = "THROUGHPUT"
    LATENCY = "LATENCY"
    RELIABILITY = "RELIABILITY"
    COST = "COST"
    SECURITY = "SECURITY"
    PORTABILITY = "PORTABILITY"
    DRIFT = "DRIFT"


class OperationKind(StrEnum):
    SET_ARTIFACT = "SET_ARTIFACT"
    DELETE_ARTIFACT = "DELETE_ARTIFACT"
    APPEND_ARTIFACT = "APPEND_ARTIFACT"
    REGISTER_CAPABILITY = "REGISTER_CAPABILITY"
    BIND_ADAPTER = "BIND_ADAPTER"


class TelemetrySource(StrEnum):
    OBSERVED_LOCAL = "OBSERVED_LOCAL"
    SYNTHETIC_SHADOW = "SYNTHETIC_SHADOW"
    EXTERNAL_RECEIPT = "EXTERNAL_RECEIPT"


class TerminalStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    AWAITING_OPERATOR = "AWAITING_OPERATOR"
    ROLLED_BACK = "ROLLED_BACK"


class ResourceBudget(StrictContract):
    maximum_operations: int = Field(default=32, ge=1, le=10_000)
    maximum_compute_units: int = Field(default=100, ge=1, le=1_000_000)
    maximum_memory_mb: int = Field(default=512, ge=16, le=1_048_576)
    maximum_output_bytes: int = Field(default=1_000_000, ge=1, le=100_000_000)
    maximum_cycles: int = Field(default=12, ge=1, le=100)


class ResourceUse(StrictContract):
    operations: int = Field(default=0, ge=0)
    compute_units: int = Field(default=0, ge=0)
    peak_memory_mb: int = Field(default=0, ge=0)
    output_bytes: int = Field(default=0, ge=0)

    def within(self, budget: ResourceBudget) -> bool:
        return all(
            (
                self.operations <= budget.maximum_operations,
                self.compute_units <= budget.maximum_compute_units,
                self.peak_memory_mb <= budget.maximum_memory_mb,
                self.output_bytes <= budget.maximum_output_bytes,
            )
        )


class FitnessTargets(StrictContract):
    minimum_quality: float = Field(default=0.85, ge=0.0, le=1.0)
    minimum_throughput: float = Field(default=1.0, gt=0.0)
    maximum_latency_ms: float = Field(default=1_000.0, gt=0.0)
    maximum_error_rate: float = Field(default=0.02, ge=0.0, le=1.0)
    maximum_drift: float = Field(default=0.05, ge=0.0, le=1.0)
    maximum_cost_units: float = Field(default=1.0, gt=0.0)
    maximum_security_findings: int = Field(default=0, ge=0)
    minimum_portability: float = Field(default=0.80, ge=0.0, le=1.0)


class FitnessWeights(StrictContract):
    quality: float = Field(default=2.0, ge=0.0)
    throughput: float = Field(default=1.0, ge=0.0)
    latency: float = Field(default=1.0, ge=0.0)
    reliability: float = Field(default=2.0, ge=0.0)
    drift: float = Field(default=1.0, ge=0.0)
    cost: float = Field(default=1.0, ge=0.0)
    security: float = Field(default=3.0, ge=0.0)
    portability: float = Field(default=2.0, ge=0.0)

    @model_validator(mode="after")
    def nonzero_total(self) -> "FitnessWeights":
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("fitness weights must have a positive total")
        return self


class AutopoieticPolicy(StrictContract):
    policy_version: str = Field(min_length=3, max_length=120)
    targets: FitnessTargets = Field(default_factory=FitnessTargets)
    weights: FitnessWeights = Field(default_factory=FitnessWeights)
    budget: ResourceBudget = Field(default_factory=ResourceBudget)
    minimum_shadow_fitness_delta: float = Field(default=0.01, ge=0.0, le=1.0)
    maximum_proposals_per_cycle: int = Field(default=3, ge=1, le=12)
    no_progress_limit: int = Field(default=2, ge=1, le=12)
    autonomous_effects: tuple[EffectClass, ...] = (
        EffectClass.PURE,
        EffectClass.READ_LOCAL,
        EffectClass.WRITE_REVERSIBLE,
    )
    operator_required_effects: tuple[EffectClass, ...] = (
        EffectClass.READ_EXTERNAL,
        EffectClass.WRITE_COMPENSATABLE,
        EffectClass.WRITE_IRREVERSIBLE,
        EffectClass.FINANCIAL,
        EffectClass.COMMUNICATION,
        EffectClass.DEPLOYMENT,
        EffectClass.SECURITY_SENSITIVE,
    )
    prohibited_effects: tuple[EffectClass, ...] = ()
    network_egress_allowed: Literal[False] = False
    ambient_credentials_allowed: Literal[False] = False
    self_authority_allowed: Literal[False] = False
    self_merge_allowed: Literal[False] = False
    canonical_state_write_allowed: Literal[False] = False
    shadow_hot_reload_allowed: Literal[True] = True
    independent_verification_required: Literal[True] = True

    @model_validator(mode="after")
    def effect_sets_are_disjoint(self) -> "AutopoieticPolicy":
        groups = [
            set(self.autonomous_effects),
            set(self.operator_required_effects),
            set(self.prohibited_effects),
        ]
        if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
            raise ValueError("effect policy groups must be disjoint")
        covered = groups[0] | groups[1] | groups[2]
        if covered != set(EffectClass):
            missing = sorted(effect.value for effect in set(EffectClass) - covered)
            raise ValueError("effect policy must classify every effect: " + ", ".join(missing))
        return self


class ObjectiveContract(StrictContract):
    objective_id: str = Field(pattern=r"^OBJ-[A-Z0-9_-]{6,80}$")
    revision: int = Field(ge=1, le=1_000_000)
    objective: str = Field(min_length=8, max_length=8_000)
    target_component: str = Field(min_length=3, max_length=240)
    acceptance_criteria: tuple[str, ...] = Field(min_length=1, max_length=32)
    explicit_exclusions: tuple[str, ...] = Field(default=(), max_length=32)
    exact_repository_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    effect_ceiling: EffectClass
    risk_tier: Literal["R0", "R1", "R2", "R3", "R4"]
    sealed: Literal[True] = True

    @computed_field
    @property
    def digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"digest"}))


class EcosystemState(StrictContract):
    state_id: str = Field(pattern=r"^ECO-STATE-[A-Z0-9_-]{6,80}$")
    revision: int = Field(default=0, ge=0, le=1_000_000)
    exact_repository_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    artifacts: dict[str, Any] = Field(default_factory=dict, max_length=1_000)
    capabilities: tuple[str, ...] = Field(default=(), max_length=256)
    adapter_bindings: dict[str, str] = Field(default_factory=dict, max_length=128)
    emergency_stop_active: bool = False
    shadow_only: Literal[True] = True
    canonical_state: Literal[False] = False

    @model_validator(mode="after")
    def unique_capabilities(self) -> "EcosystemState":
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("capabilities must be unique")
        return self

    @computed_field
    @property
    def digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"digest"}))


class TelemetrySnapshot(StrictContract):
    telemetry_id: str = Field(pattern=r"^TELEM-[A-Z0-9_-]{6,80}$")
    source: TelemetrySource
    observed_epoch: int = Field(ge=0)
    state_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_revision: str = Field(min_length=1, max_length=240)
    quality: float = Field(ge=0.0, le=1.0)
    throughput: float = Field(ge=0.0)
    latency_ms: float = Field(ge=0.0)
    error_rate: float = Field(ge=0.0, le=1.0)
    drift: float = Field(ge=0.0, le=1.0)
    cost_units: float = Field(ge=0.0)
    security_findings: int = Field(ge=0)
    portability: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=64)

    @computed_field
    @property
    def digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"digest"}))


class Deficit(StrictContract):
    deficit_id: str = Field(pattern=r"^DEFICIT-[A-Z0-9_-]{6,80}$")
    classification: DeficitClass
    severity: float = Field(gt=0.0, le=1.0)
    observed: float
    target: float
    rationale: str = Field(min_length=8, max_length=1_000)


class MetricImpact(StrictContract):
    metric: Literal[
        "quality",
        "throughput",
        "latency_ms",
        "error_rate",
        "drift",
        "cost_units",
        "security_findings",
        "portability",
    ]
    delta: float


class PatchOperation(StrictContract):
    operation_id: str = Field(pattern=r"^ECO-OP-[A-Z0-9_-]{6,80}$")
    kind: OperationKind
    target: str = Field(min_length=1, max_length=240)
    value: Any = None
    effect_class: EffectClass
    reversible: bool
    rollback_supported: bool
    rollback_value: Any = None
    depends_on: tuple[str, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def reversible_operations_need_rollback(self) -> "PatchOperation":
        if self.reversible and not self.rollback_supported:
            raise ValueError("reversible operation must provide rollback support")
        if self.effect_class == EffectClass.WRITE_REVERSIBLE and not self.reversible:
            raise ValueError("WRITE_REVERSIBLE operation must be reversible")
        return self


class CandidateTemplate(StrictContract):
    template_id: str = Field(pattern=r"^ECO-TEMPLATE-[A-Z0-9_-]{6,80}$")
    deficit_class: DeficitClass
    priority: int = Field(ge=0, le=1_000)
    description: str = Field(min_length=8, max_length=1_000)
    effect_class: EffectClass
    operations: tuple[PatchOperation, ...] = Field(min_length=1, max_length=32)
    metric_impacts: tuple[MetricImpact, ...] = Field(min_length=1, max_length=16)
    resource_estimate: ResourceUse
    evidence_requirements: tuple[str, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def template_effect_ceiling(self) -> "CandidateTemplate":
        if any(effect_rank(op.effect_class) > effect_rank(self.effect_class) for op in self.operations):
            raise ValueError("operation effect exceeds template effect class")
        return self


class ChangeCandidate(StrictContract):
    candidate_id: str = Field(pattern=r"^ECO-CAND-[A-Z0-9_-]{6,80}$")
    run_id: str = Field(pattern=r"^ECO-RUN-[A-Z0-9_-]{6,80}$")
    objective_id: str
    objective_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parent_state_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    exact_repository_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    producer_id: str = Field(min_length=3, max_length=120)
    deficit: Deficit
    template_id: str
    effect_class: EffectClass
    operations: tuple[PatchOperation, ...] = Field(min_length=1, max_length=32)
    predicted_metric_impacts: tuple[MetricImpact, ...] = Field(min_length=1, max_length=16)
    resource_estimate: ResourceUse
    evidence_requirements: tuple[str, ...] = Field(min_length=1, max_length=32)
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def operation_graph_is_acyclic(self) -> "ChangeCandidate":
        ids = [op.operation_id for op in self.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate operation IDs must be unique")
        known = set(ids)
        deps = {op.operation_id: set(op.depends_on) for op in self.operations}
        for op_id, required in deps.items():
            unknown = required - known
            if unknown:
                raise ValueError(f"{op_id} has unknown dependencies: {sorted(unknown)}")
            if op_id in required:
                raise ValueError(f"{op_id} cannot depend on itself")
        remaining = set(ids)
        resolved: set[str] = set()
        while remaining:
            ready = {op_id for op_id in remaining if deps[op_id] <= resolved}
            if not ready:
                raise ValueError("candidate operation graph contains a cycle")
            resolved.update(ready)
            remaining.difference_update(ready)
        return self

    @computed_field
    @property
    def digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"digest"}))


class VerificationGate(StrictContract):
    gate_id: str = Field(pattern=r"^GATE-[A-Z0-9_-]{3,100}$")
    result: GateResult
    detail: str = Field(min_length=3, max_length=2_000)
    evidence_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class VerificationReport(StrictContract):
    report_id: str = Field(pattern=r"^ECO-VERIFY-[A-Z0-9_-]{6,80}$")
    candidate_id: str
    candidate_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    producer_id: str
    verifier_id: str
    independent: bool
    parent_state_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    fitness_before: float = Field(ge=0.0, le=1.0)
    predicted_fitness_after: float = Field(ge=0.0, le=1.0)
    gates: tuple[VerificationGate, ...] = Field(min_length=1, max_length=64)
    approved_for_local_shadow: bool
    first_blocker: str | None = None

    @model_validator(mode="after")
    def enforce_independence(self) -> "VerificationReport":
        if self.independent and self.producer_id == self.verifier_id:
            raise ValueError("producer cannot self-assert independent verification")
        if self.approved_for_local_shadow and any(g.result != GateResult.PASS for g in self.gates):
            raise ValueError("shadow approval requires every gate to pass")
        return self

    @computed_field
    @property
    def digest(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"digest"}))


class CycleRequest(StrictContract):
    run_id: str = Field(pattern=r"^ECO-RUN-[A-Z0-9_-]{6,80}$")
    objective: ObjectiveContract
    state: EcosystemState
    telemetry: TelemetrySnapshot
    mode: Literal["PLAN_ONLY", "LOCAL_SHADOW"] = "LOCAL_SHADOW"
    previous_receipt_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    producer_id: str = Field(default="AGT-AUTOPOIETIC-SYNTHESIZER", min_length=3, max_length=120)
    verifier_id: str = Field(default="AGT-OMEGA-INDEPENDENT-VERIFIER", min_length=3, max_length=120)


class CycleReceipt(StrictContract):
    schema_version: Literal["aigc.autopoietic-cycle-receipt.v1"]
    receipt_id: str = Field(pattern=r"^ECO-RCPT-[A-Z0-9_-]{6,80}$")
    run_id: str
    phase: CyclePhase
    terminal_status: TerminalStatus
    reason: str = Field(min_length=3, max_length=2_000)
    exact_repository_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    objective_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    telemetry_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parent_state_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    resulting_state_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    verification_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    previous_receipt_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    proposed: bool
    approved_for_shadow: bool
    executed_in_shadow: bool
    verified: bool
    promoted_to_shadow: bool
    rolled_back: bool
    operator_action_required: bool
    canonical_state_mutated: Literal[False] = False
    external_action_performed: Literal[False] = False
    network_calls_performed: Literal[0] = 0
    provider_calls_performed: Literal[0] = 0
    processes_spawned: Literal[0] = 0
    filesystem_writes_performed: Literal[0] = 0
    secrets_accessed: Literal[0] = 0
    logical_shadow_mutations: int = Field(default=0, ge=0)
    resource_use: ResourceUse = Field(default_factory=ResourceUse)
    events: tuple[str, ...] = Field(default=(), max_length=128)
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def semantic_consistency(self) -> "CycleReceipt":
        if self.promoted_to_shadow and not all(
            (self.proposed, self.approved_for_shadow, self.executed_in_shadow, self.verified)
        ):
            raise ValueError("promotion requires proposed, approved, executed, and verified")
        if self.rolled_back and self.promoted_to_shadow:
            raise ValueError("receipt cannot be both promoted and rolled back")
        if self.operator_action_required and self.executed_in_shadow:
            raise ValueError("operator-blocked receipt cannot claim execution")
        return self

    def verify_hash(self) -> bool:
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        return self.receipt_sha256 == canonical_sha256(payload)

    @classmethod
    def seal(cls, payload: dict[str, Any]) -> "CycleReceipt":
        seed = dict(payload)
        seed.pop("receipt_sha256", None)
        seed["receipt_sha256"] = canonical_sha256(seed)
        return cls.model_validate(seed)


class CycleResult(StrictContract):
    state: EcosystemState
    receipt: CycleReceipt
    deficits: tuple[Deficit, ...] = ()
    candidate: ChangeCandidate | None = None
    verification: VerificationReport | None = None
    shadow_telemetry: TelemetrySnapshot | None = None
