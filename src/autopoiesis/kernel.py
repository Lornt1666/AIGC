from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Iterable

from .contracts import (
    AutopoieticPolicy,
    CandidateTemplate,
    ChangeCandidate,
    CyclePhase,
    CycleReceipt,
    CycleRequest,
    CycleResult,
    Deficit,
    DeficitClass,
    EcosystemState,
    EffectClass,
    GateResult,
    MetricImpact,
    OperationKind,
    PatchOperation,
    ResourceUse,
    TelemetrySnapshot,
    TelemetrySource,
    TerminalStatus,
    VerificationGate,
    VerificationReport,
    canonical_sha256,
    effect_rank,
    stable_id,
)


_RAW_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "private_key",
    "credential",
    "credentials",
    "access_token",
    "refresh_token",
    "api_key",
}


def _contains_raw_secret(value: Any, *, key: str | None = None) -> bool:
    if key is not None and key.lower() in _SENSITIVE_KEYS:
        return True
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _RAW_SECRET_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_raw_secret(item, key=str(name)) for name, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_raw_secret(item) for item in value)
    return False


def compute_fitness(snapshot: TelemetrySnapshot, policy: AutopoieticPolicy) -> float:
    targets = policy.targets
    weights = policy.weights
    components = {
        "quality": snapshot.quality,
        "throughput": min(snapshot.throughput / targets.minimum_throughput, 1.0),
        "latency": 1.0 - min(snapshot.latency_ms / targets.maximum_latency_ms, 1.0),
        "reliability": 1.0 - snapshot.error_rate,
        "drift": 1.0 - snapshot.drift,
        "cost": 1.0 - min(snapshot.cost_units / targets.maximum_cost_units, 1.0),
        "security": 1.0
        if snapshot.security_findings <= targets.maximum_security_findings
        else max(
            0.0,
            1.0
            - (
                snapshot.security_findings - targets.maximum_security_findings
            )
            / max(snapshot.security_findings, 1),
        ),
        "portability": snapshot.portability,
    }
    weight_payload = weights.model_dump()
    total = sum(weight_payload.values())
    score = sum(components[name] * weight_payload[name] for name in components) / total
    return round(max(0.0, min(score, 1.0)), 12)


def detect_deficits(snapshot: TelemetrySnapshot, policy: AutopoieticPolicy) -> tuple[Deficit, ...]:
    t = policy.targets
    candidates: list[tuple[DeficitClass, float, float, float, str]] = []
    if snapshot.quality < t.minimum_quality:
        candidates.append(
            (
                DeficitClass.QUALITY,
                (t.minimum_quality - snapshot.quality) / max(t.minimum_quality, 1e-12),
                snapshot.quality,
                t.minimum_quality,
                "generation quality is below the sealed minimum",
            )
        )
    if snapshot.throughput < t.minimum_throughput:
        candidates.append(
            (
                DeficitClass.THROUGHPUT,
                (t.minimum_throughput - snapshot.throughput) / t.minimum_throughput,
                snapshot.throughput,
                t.minimum_throughput,
                "throughput is below the target floor",
            )
        )
    if snapshot.latency_ms > t.maximum_latency_ms:
        candidates.append(
            (
                DeficitClass.LATENCY,
                min((snapshot.latency_ms - t.maximum_latency_ms) / max(snapshot.latency_ms, 1.0), 1.0),
                snapshot.latency_ms,
                t.maximum_latency_ms,
                "latency exceeds the target ceiling",
            )
        )
    if snapshot.error_rate > t.maximum_error_rate:
        candidates.append(
            (
                DeficitClass.RELIABILITY,
                min((snapshot.error_rate - t.maximum_error_rate) / max(snapshot.error_rate, 1e-12), 1.0),
                snapshot.error_rate,
                t.maximum_error_rate,
                "error rate exceeds the reliability ceiling",
            )
        )
    if snapshot.cost_units > t.maximum_cost_units:
        candidates.append(
            (
                DeficitClass.COST,
                min((snapshot.cost_units - t.maximum_cost_units) / max(snapshot.cost_units, 1e-12), 1.0),
                snapshot.cost_units,
                t.maximum_cost_units,
                "resource cost exceeds the sealed ceiling",
            )
        )
    if snapshot.security_findings > t.maximum_security_findings:
        candidates.append(
            (
                DeficitClass.SECURITY,
                min(
                    (snapshot.security_findings - t.maximum_security_findings)
                    / max(snapshot.security_findings, 1),
                    1.0,
                ),
                float(snapshot.security_findings),
                float(t.maximum_security_findings),
                "security findings remain unresolved",
            )
        )
    if snapshot.portability < t.minimum_portability:
        candidates.append(
            (
                DeficitClass.PORTABILITY,
                (t.minimum_portability - snapshot.portability) / max(t.minimum_portability, 1e-12),
                snapshot.portability,
                t.minimum_portability,
                "hardware or provider portability is below the target floor",
            )
        )
    if snapshot.drift > t.maximum_drift:
        candidates.append(
            (
                DeficitClass.DRIFT,
                min((snapshot.drift - t.maximum_drift) / max(snapshot.drift, 1e-12), 1.0),
                snapshot.drift,
                t.maximum_drift,
                "semantic or behavioral drift exceeds the target ceiling",
            )
        )

    deficits = [
        Deficit(
            deficit_id=stable_id(
                "DEFICIT",
                {
                    "telemetry": snapshot.telemetry_id,
                    "classification": classification.value,
                    "observed": observed,
                    "target": target,
                },
            ),
            classification=classification,
            severity=round(max(1e-12, min(severity, 1.0)), 12),
            observed=observed,
            target=target,
            rationale=rationale,
        )
        for classification, severity, observed, target, rationale in candidates
    ]
    return tuple(sorted(deficits, key=lambda item: (-item.severity, item.classification.value)))


def _apply_metric_impacts(
    snapshot: TelemetrySnapshot,
    impacts: Iterable[MetricImpact],
    *,
    resulting_state_sha256: str,
    run_id: str,
) -> TelemetrySnapshot:
    payload = snapshot.model_dump(mode="python", exclude={"digest"})
    for impact in impacts:
        current = payload[impact.metric]
        next_value = current + impact.delta
        if impact.metric in {"quality", "error_rate", "drift", "portability"}:
            next_value = max(0.0, min(float(next_value), 1.0))
        elif impact.metric == "security_findings":
            next_value = max(0, int(round(next_value)))
        else:
            next_value = max(0.0, float(next_value))
        payload[impact.metric] = next_value
    payload.update(
        {
            "telemetry_id": stable_id(
                "TELEM",
                {
                    "run_id": run_id,
                    "prior": snapshot.digest,
                    "state": resulting_state_sha256,
                    "impacts": [item.model_dump(mode="json") for item in impacts],
                },
            ),
            "source": TelemetrySource.SYNTHETIC_SHADOW,
            "observed_epoch": snapshot.observed_epoch + 1,
            "state_sha256": resulting_state_sha256,
            "source_revision": run_id,
            "evidence_refs": (
                *snapshot.evidence_refs,
                f"shadow://autopoiesis/{run_id}",
            ),
        }
    )
    return TelemetrySnapshot.model_validate(payload)


def _candidate_effect(operations: Iterable[PatchOperation]) -> EffectClass:
    values = tuple(operations)
    return max((item.effect_class for item in values), key=effect_rank)


def _build_candidate(
    request: CycleRequest,
    deficit: Deficit,
    template: CandidateTemplate,
) -> ChangeCandidate:
    seed = {
        "run_id": request.run_id,
        "objective_sha256": request.objective.digest,
        "parent_state_sha256": request.state.digest,
        "deficit": deficit.model_dump(mode="json"),
        "template": template.model_dump(mode="json"),
        "producer_id": request.producer_id,
    }
    candidate_id = stable_id("ECO-CAND", seed)
    return ChangeCandidate(
        candidate_id=candidate_id,
        run_id=request.run_id,
        objective_id=request.objective.objective_id,
        objective_sha256=request.objective.digest,
        parent_state_sha256=request.state.digest,
        exact_repository_revision=request.state.exact_repository_revision,
        producer_id=request.producer_id,
        deficit=deficit,
        template_id=template.template_id,
        effect_class=_candidate_effect(template.operations),
        operations=template.operations,
        predicted_metric_impacts=template.metric_impacts,
        resource_estimate=template.resource_estimate,
        evidence_requirements=template.evidence_requirements,
        idempotency_key=canonical_sha256(
            {
                "candidate_id": candidate_id,
                "parent_state_sha256": request.state.digest,
                "objective_sha256": request.objective.digest,
            }
        ),
    )


def _gate(gate_id: str, passed: bool, detail: str, *, blocked: bool = False) -> VerificationGate:
    result = GateResult.PASS if passed else (GateResult.BLOCKED if blocked else GateResult.FAIL)
    return VerificationGate(
        gate_id=gate_id,
        result=result,
        detail=detail,
        evidence_sha256=canonical_sha256({"gate_id": gate_id, "result": result.value, "detail": detail}),
    )


def verify_candidate(
    request: CycleRequest,
    candidate: ChangeCandidate,
    policy: AutopoieticPolicy,
) -> VerificationReport:
    fitness_before = compute_fitness(request.telemetry, policy)
    synthetic = _apply_metric_impacts(
        request.telemetry,
        candidate.predicted_metric_impacts,
        resulting_state_sha256=request.state.digest,
        run_id=request.run_id,
    )
    predicted_after = compute_fitness(synthetic, policy)
    independent = request.producer_id != request.verifier_id
    autonomous = candidate.effect_class in policy.autonomous_effects
    operator_required = candidate.effect_class in policy.operator_required_effects
    prohibited = candidate.effect_class in policy.prohibited_effects
    gates = (
        _gate(
            "GATE-EXACT-REVISION",
            candidate.exact_repository_revision
            == request.objective.exact_repository_revision
            == request.state.exact_repository_revision,
            "candidate, objective, and state bind the same exact repository revision",
        ),
        _gate(
            "GATE-PARENT-STATE",
            candidate.parent_state_sha256 == request.state.digest,
            "candidate is bound to the exact current state digest",
        ),
        _gate(
            "GATE-INDEPENDENT-VERIFIER",
            independent,
            "verifier lineage differs from producer lineage",
        ),
        _gate(
            "GATE-EFFECT-CEILING",
            effect_rank(candidate.effect_class) <= effect_rank(request.objective.effect_ceiling),
            "candidate effect does not exceed the sealed objective ceiling",
        ),
        _gate(
            "GATE-POLICY-EFFECT",
            autonomous and not operator_required and not prohibited,
            (
                "effect is permitted for autonomous local shadow execution"
                if autonomous and not prohibited
                else "effect requires operator authority or is prohibited"
            ),
            blocked=operator_required or prohibited,
        ),
        _gate(
            "GATE-BUDGET",
            candidate.resource_estimate.within(policy.budget),
            "candidate resource estimate remains within all sealed ceilings",
        ),
        _gate(
            "GATE-ROLLBACK",
            all(
                op.effect_class != EffectClass.WRITE_REVERSIBLE
                or (op.reversible and op.rollback_supported)
                for op in candidate.operations
            ),
            "every reversible mutation has an explicit rollback path",
        ),
        _gate(
            "GATE-SECRETS",
            not _contains_raw_secret(candidate.model_dump(mode="python")),
            "candidate contains no raw secret-shaped material",
        ),
        _gate(
            "GATE-NO-EGRESS",
            policy.network_egress_allowed is False,
            "autopoietic local shadow execution has no network egress",
        ),
        _gate(
            "GATE-FITNESS",
            predicted_after - fitness_before >= policy.minimum_shadow_fitness_delta,
            "predicted local shadow fitness meets the minimum improvement delta",
        ),
        _gate(
            "GATE-EVIDENCE-CONTRACT",
            bool(candidate.evidence_requirements)
            and bool(request.objective.acceptance_criteria),
            "candidate and objective both define evidence and acceptance obligations",
        ),
    )
    approved = all(item.result == GateResult.PASS for item in gates)
    first_blocker = next(
        (item.gate_id for item in gates if item.result != GateResult.PASS),
        None,
    )
    seed = {
        "candidate_sha256": candidate.digest,
        "verifier_id": request.verifier_id,
        "gates": [item.model_dump(mode="json") for item in gates],
        "fitness_before": fitness_before,
        "predicted_after": predicted_after,
    }
    return VerificationReport(
        report_id=stable_id("ECO-VERIFY", seed),
        candidate_id=candidate.candidate_id,
        candidate_sha256=candidate.digest,
        producer_id=request.producer_id,
        verifier_id=request.verifier_id,
        independent=independent,
        parent_state_sha256=request.state.digest,
        fitness_before=fitness_before,
        predicted_fitness_after=predicted_after,
        gates=gates,
        approved_for_local_shadow=approved,
        first_blocker=first_blocker,
    )


class InMemorySandbox:
    """Deterministic local shadow adapter with no network, process, or filesystem access."""

    def __init__(self) -> None:
        self._consumed_idempotency_keys: set[str] = set()

    @property
    def consumed_count(self) -> int:
        return len(self._consumed_idempotency_keys)

    def apply(
        self,
        state: EcosystemState,
        candidate: ChangeCandidate,
        policy: AutopoieticPolicy,
    ) -> tuple[EcosystemState, tuple[str, ...], ResourceUse]:
        if candidate.idempotency_key in self._consumed_idempotency_keys:
            raise ValueError("candidate idempotency key has already been consumed")
        if not candidate.resource_estimate.within(policy.budget):
            raise ValueError("candidate resource use exceeds sealed budget")
        if candidate.parent_state_sha256 != state.digest:
            raise ValueError("stale candidate parent state")
        if candidate.effect_class not in policy.autonomous_effects:
            raise PermissionError("candidate effect is not autonomous-local eligible")

        artifacts = deepcopy(state.artifacts)
        capabilities = set(state.capabilities)
        adapters = dict(state.adapter_bindings)
        events: list[str] = []
        applied: set[str] = set()
        remaining = {op.operation_id: op for op in candidate.operations}
        while remaining:
            ready = [
                op
                for op in remaining.values()
                if set(op.depends_on) <= applied
            ]
            if not ready:
                raise ValueError("operation graph could not be scheduled")
            for op in sorted(ready, key=lambda item: item.operation_id):
                if op.kind == OperationKind.SET_ARTIFACT:
                    artifacts[op.target] = deepcopy(op.value)
                elif op.kind == OperationKind.DELETE_ARTIFACT:
                    artifacts.pop(op.target, None)
                elif op.kind == OperationKind.APPEND_ARTIFACT:
                    current = artifacts.setdefault(op.target, [])
                    if not isinstance(current, list):
                        raise TypeError(f"artifact {op.target} is not appendable")
                    current.append(deepcopy(op.value))
                elif op.kind == OperationKind.REGISTER_CAPABILITY:
                    capabilities.add(str(op.value))
                elif op.kind == OperationKind.BIND_ADAPTER:
                    adapters[op.target] = str(op.value)
                else:  # pragma: no cover - exhaustive enum guard
                    raise ValueError(f"unsupported operation kind: {op.kind}")
                events.append(f"SHADOW_APPLIED:{op.operation_id}:{op.kind.value}:{op.target}")
                applied.add(op.operation_id)
                remaining.pop(op.operation_id)

        self._consumed_idempotency_keys.add(candidate.idempotency_key)
        next_state = state.model_copy(
            update={
                "revision": state.revision + 1,
                "artifacts": artifacts,
                "capabilities": tuple(sorted(capabilities)),
                "adapter_bindings": adapters,
            }
        )
        return next_state, tuple(events), candidate.resource_estimate


class ReceiptLedger:
    """Append-only in-memory receipt chain used by one local process."""

    def __init__(self) -> None:
        self._receipts: list[CycleReceipt] = []
        self._receipt_ids: set[str] = set()

    @property
    def last_sha256(self) -> str | None:
        return self._receipts[-1].receipt_sha256 if self._receipts else None

    @property
    def receipts(self) -> tuple[CycleReceipt, ...]:
        return tuple(self._receipts)

    def append(self, receipt: CycleReceipt) -> None:
        if not receipt.verify_hash():
            raise ValueError("receipt hash verification failed")
        if receipt.receipt_id in self._receipt_ids:
            raise ValueError("receipt replay detected")
        if receipt.previous_receipt_sha256 != self.last_sha256:
            raise ValueError("receipt chain predecessor mismatch")
        self._receipt_ids.add(receipt.receipt_id)
        self._receipts.append(receipt)

    @staticmethod
    def verify_chain(receipts: Iterable[CycleReceipt]) -> bool:
        previous: str | None = None
        seen: set[str] = set()
        for receipt in receipts:
            if receipt.receipt_id in seen or not receipt.verify_hash():
                return False
            if receipt.previous_receipt_sha256 != previous:
                return False
            seen.add(receipt.receipt_id)
            previous = receipt.receipt_sha256
        return True


class AutopoieticKernel:
    """Finite, deterministic, local-first autopoietic cycle coordinator."""

    def __init__(
        self,
        *,
        policy: AutopoieticPolicy,
        templates: Iterable[CandidateTemplate],
        sandbox: InMemorySandbox | None = None,
        ledger: ReceiptLedger | None = None,
    ) -> None:
        self.policy = policy
        self.templates = tuple(templates)
        self.sandbox = sandbox or InMemorySandbox()
        self.ledger = ledger or ReceiptLedger()

    def _select_template(self, deficit: Deficit) -> CandidateTemplate | None:
        candidates = [
            item for item in self.templates if item.deficit_class == deficit.classification
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (item.priority, item.template_id))[0]

    def _seal_receipt(
        self,
        request: CycleRequest,
        *,
        phase: CyclePhase,
        terminal_status: TerminalStatus,
        reason: str,
        state: EcosystemState,
        candidate: ChangeCandidate | None = None,
        verification: VerificationReport | None = None,
        proposed: bool = False,
        approved_for_shadow: bool = False,
        executed_in_shadow: bool = False,
        verified: bool = False,
        promoted_to_shadow: bool = False,
        rolled_back: bool = False,
        operator_action_required: bool = False,
        resource_use: ResourceUse | None = None,
        events: tuple[str, ...] = (),
        logical_shadow_mutations: int = 0,
    ) -> CycleReceipt:
        predecessor = self.ledger.last_sha256
        if request.previous_receipt_sha256 != predecessor:
            raise ValueError("request previous receipt does not match ledger head")
        seed = {
            "run_id": request.run_id,
            "phase": phase.value,
            "terminal_status": terminal_status.value,
            "parent": request.state.digest,
            "result": state.digest,
            "candidate": candidate.digest if candidate else None,
            "verification": verification.digest if verification else None,
            "previous": predecessor,
            "reason": reason,
        }
        receipt = CycleReceipt.seal(
            {
                "schema_version": "aigc.autopoietic-cycle-receipt.v1",
                "receipt_id": stable_id("ECO-RCPT", seed),
                "run_id": request.run_id,
                "phase": phase,
                "terminal_status": terminal_status,
                "reason": reason,
                "exact_repository_revision": request.state.exact_repository_revision,
                "objective_sha256": request.objective.digest,
                "telemetry_sha256": request.telemetry.digest,
                "parent_state_sha256": request.state.digest,
                "resulting_state_sha256": state.digest,
                "candidate_sha256": candidate.digest if candidate else None,
                "verification_sha256": verification.digest if verification else None,
                "previous_receipt_sha256": predecessor,
                "proposed": proposed,
                "approved_for_shadow": approved_for_shadow,
                "executed_in_shadow": executed_in_shadow,
                "verified": verified,
                "promoted_to_shadow": promoted_to_shadow,
                "rolled_back": rolled_back,
                "operator_action_required": operator_action_required,
                "canonical_state_mutated": False,
                "external_action_performed": False,
                "network_calls_performed": 0,
                "provider_calls_performed": 0,
                "processes_spawned": 0,
                "filesystem_writes_performed": 0,
                "secrets_accessed": 0,
                "logical_shadow_mutations": logical_shadow_mutations,
                "resource_use": resource_use or ResourceUse(),
                "events": events,
            }
        )
        self.ledger.append(receipt)
        return receipt

    def run_cycle(self, request: CycleRequest) -> CycleResult:
        if request.previous_receipt_sha256 != self.ledger.last_sha256:
            raise ValueError("request is not bound to the current receipt chain head")
        if request.state.emergency_stop_active:
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.BLOCKED,
                terminal_status=TerminalStatus.BLOCKED,
                reason="EMERGENCY_STOP_ACTIVE",
                state=request.state,
                events=("SENSE:EMERGENCY_STOP",),
            )
            return CycleResult(state=request.state, receipt=receipt)
        if request.state.exact_repository_revision != request.objective.exact_repository_revision:
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.BLOCKED,
                terminal_status=TerminalStatus.BLOCKED,
                reason="STALE_REPOSITORY_REVISION",
                state=request.state,
                events=("SENSE:REVISION_MISMATCH",),
            )
            return CycleResult(state=request.state, receipt=receipt)
        if request.telemetry.state_sha256 != request.state.digest:
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.BLOCKED,
                terminal_status=TerminalStatus.BLOCKED,
                reason="TELEMETRY_STATE_HASH_MISMATCH",
                state=request.state,
                events=("SENSE:STALE_TELEMETRY",),
            )
            return CycleResult(state=request.state, receipt=receipt)

        deficits = detect_deficits(request.telemetry, self.policy)
        if not deficits:
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.NO_CHANGE_REQUIRED,
                terminal_status=TerminalStatus.PASS,
                reason="FITNESS_TARGETS_SATISFIED",
                state=request.state,
                events=("SENSE:NO_DEFICIT",),
            )
            return CycleResult(state=request.state, receipt=receipt, deficits=deficits)

        deficit = deficits[0]
        template = self._select_template(deficit)
        if template is None:
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.BLOCKED,
                terminal_status=TerminalStatus.BLOCKED,
                reason=f"NO_ADMISSIBLE_TEMPLATE:{deficit.classification.value}",
                state=request.state,
                events=(f"FORMULATE:UNRESOLVED:{deficit.deficit_id}",),
            )
            return CycleResult(state=request.state, receipt=receipt, deficits=deficits)

        candidate = _build_candidate(request, deficit, template)
        verification = verify_candidate(request, candidate, self.policy)
        effect_operator_required = candidate.effect_class in self.policy.operator_required_effects
        effect_prohibited = candidate.effect_class in self.policy.prohibited_effects
        if effect_operator_required or effect_prohibited:
            reason = (
                f"OPERATOR_AUTHORITY_REQUIRED:{candidate.effect_class.value}"
                if effect_operator_required
                else f"EFFECT_PROHIBITED:{candidate.effect_class.value}"
            )
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.AWAITING_OPERATOR if effect_operator_required else CyclePhase.BLOCKED,
                terminal_status=(
                    TerminalStatus.AWAITING_OPERATOR
                    if effect_operator_required
                    else TerminalStatus.BLOCKED
                ),
                reason=reason,
                state=request.state,
                candidate=candidate,
                verification=verification,
                proposed=True,
                approved_for_shadow=False,
                verified=False,
                operator_action_required=effect_operator_required,
                events=(
                    f"SENSE:{deficit.deficit_id}",
                    f"FORMULATE:{template.template_id}",
                    f"SYNTHESIZE:{candidate.candidate_id}",
                    f"VERIFY:{verification.first_blocker or 'POLICY_AUTHORITY_BOUNDARY'}",
                ),
            )
            return CycleResult(
                state=request.state,
                receipt=receipt,
                deficits=deficits,
                candidate=candidate,
                verification=verification,
            )

        if not verification.approved_for_local_shadow:
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.BLOCKED,
                terminal_status=TerminalStatus.BLOCKED,
                reason=f"VERIFICATION_FAILED:{verification.first_blocker}",
                state=request.state,
                candidate=candidate,
                verification=verification,
                proposed=True,
                verified=False,
                events=(
                    f"SENSE:{deficit.deficit_id}",
                    f"FORMULATE:{template.template_id}",
                    f"SYNTHESIZE:{candidate.candidate_id}",
                    f"VERIFY:{verification.first_blocker}",
                ),
            )
            return CycleResult(
                state=request.state,
                receipt=receipt,
                deficits=deficits,
                candidate=candidate,
                verification=verification,
            )

        if request.mode == "PLAN_ONLY":
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.VERIFIED,
                terminal_status=TerminalStatus.PASS,
                reason="PLAN_VERIFIED_NOT_EXECUTED",
                state=request.state,
                candidate=candidate,
                verification=verification,
                proposed=True,
                approved_for_shadow=True,
                verified=True,
                events=(
                    f"SENSE:{deficit.deficit_id}",
                    f"FORMULATE:{template.template_id}",
                    f"SYNTHESIZE:{candidate.candidate_id}",
                    f"VERIFY:{verification.report_id}",
                    "INSTANTIATE:SKIPPED_PLAN_ONLY",
                ),
            )
            return CycleResult(
                state=request.state,
                receipt=receipt,
                deficits=deficits,
                candidate=candidate,
                verification=verification,
            )

        next_state, sandbox_events, resource_use = self.sandbox.apply(
            request.state, candidate, self.policy
        )
        shadow_telemetry = _apply_metric_impacts(
            request.telemetry,
            candidate.predicted_metric_impacts,
            resulting_state_sha256=next_state.digest,
            run_id=request.run_id,
        )
        fitness_before = compute_fitness(request.telemetry, self.policy)
        fitness_after = compute_fitness(shadow_telemetry, self.policy)
        delta = fitness_after - fitness_before
        if delta < self.policy.minimum_shadow_fitness_delta:
            receipt = self._seal_receipt(
                request,
                phase=CyclePhase.ROLLED_BACK,
                terminal_status=TerminalStatus.ROLLED_BACK,
                reason="SHADOW_FITNESS_REGRESSION_OR_INSUFFICIENT_PROGRESS",
                state=request.state,
                candidate=candidate,
                verification=verification,
                proposed=True,
                approved_for_shadow=True,
                executed_in_shadow=True,
                verified=True,
                rolled_back=True,
                resource_use=resource_use,
                logical_shadow_mutations=len(candidate.operations),
                events=(
                    f"SENSE:{deficit.deficit_id}",
                    f"FORMULATE:{template.template_id}",
                    f"SYNTHESIZE:{candidate.candidate_id}",
                    f"VERIFY:{verification.report_id}",
                    *sandbox_events,
                    f"EVALUATE:DELTA:{delta:.12f}",
                    "ROLLBACK:LOCAL_SHADOW",
                ),
            )
            return CycleResult(
                state=request.state,
                receipt=receipt,
                deficits=deficits,
                candidate=candidate,
                verification=verification,
                shadow_telemetry=shadow_telemetry,
            )

        receipt = self._seal_receipt(
            request,
            phase=CyclePhase.PROMOTED_SHADOW,
            terminal_status=TerminalStatus.PASS,
            reason="LOCAL_SHADOW_FITNESS_IMPROVED",
            state=next_state,
            candidate=candidate,
            verification=verification,
            proposed=True,
            approved_for_shadow=True,
            executed_in_shadow=True,
            verified=True,
            promoted_to_shadow=True,
            resource_use=resource_use,
            logical_shadow_mutations=len(candidate.operations),
            events=(
                f"SENSE:{deficit.deficit_id}",
                f"FORMULATE:{template.template_id}",
                f"SYNTHESIZE:{candidate.candidate_id}",
                f"VERIFY:{verification.report_id}",
                *sandbox_events,
                f"EVALUATE:DELTA:{delta:.12f}",
                "PROMOTE:LOCAL_SHADOW_ONLY",
            ),
        )
        return CycleResult(
            state=next_state,
            receipt=receipt,
            deficits=deficits,
            candidate=candidate,
            verification=verification,
            shadow_telemetry=shadow_telemetry,
        )
