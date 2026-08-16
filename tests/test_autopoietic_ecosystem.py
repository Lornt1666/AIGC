from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import random
import subprocess
import sys

import jsonschema
import pytest
from pydantic import ValidationError

from src.autopoiesis import (
    AutopoieticKernel,
    AutopoieticPolicy,
    CandidateTemplate,
    CycleRequest,
    DeficitClass,
    EcosystemState,
    EffectClass,
    InMemorySandbox,
    MetricImpact,
    ObjectiveContract,
    OperationKind,
    PatchOperation,
    ReceiptLedger,
    ResourceUse,
    TelemetrySnapshot,
    TelemetrySource,
    canonical_sha256,
    load_ecosystem_config,
)
from src.autopoiesis.contracts import CycleReceipt, GateResult
from src.autopoiesis.kernel import _build_candidate, detect_deficits


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "aigc_autopoietic_ecosystem.v1.json"
SCHEMA = ROOT / "schemas" / "aigc_autopoietic_cycle_receipt.schema.json"
REVISION = "2a9c039e41a7d9db8410120614cde044ca785e0f"


def config():
    return load_ecosystem_config(CONFIG)


def state(**updates) -> EcosystemState:
    base = EcosystemState(
        state_id="ECO-STATE-REFERENCE-V1",
        revision=0,
        exact_repository_revision=REVISION,
        artifacts={"runtime.mode": "local-shadow"},
        capabilities=(),
        adapter_bindings={},
        emergency_stop_active=False,
    )
    return base.model_copy(update=updates)


def telemetry(current: EcosystemState, **updates) -> TelemetrySnapshot:
    payload = {
        "telemetry_id": "TELEM-REFERENCE-V1",
        "source": TelemetrySource.OBSERVED_LOCAL,
        "observed_epoch": 1,
        "state_sha256": current.digest,
        "source_revision": REVISION,
        "quality": 0.90,
        "throughput": 1.20,
        "latency_ms": 200.0,
        "error_rate": 0.01,
        "drift": 0.02,
        "cost_units": 0.50,
        "security_findings": 0,
        "portability": 0.50,
        "evidence_refs": ("local://telemetry/reference",),
    }
    payload.update(updates)
    return TelemetrySnapshot.model_validate(payload)


def objective(effect_ceiling: EffectClass = EffectClass.WRITE_REVERSIBLE, **updates) -> ObjectiveContract:
    payload = {
        "objective_id": "OBJ-AUTOPOIETIC-V1",
        "revision": 1,
        "objective": "Improve the provider and hardware portability of the local AIGC shadow ecosystem.",
        "target_component": "AIGC_AUTOPOIETIC_CONTROL_SPINE",
        "acceptance_criteria": (
            "independent verification passes",
            "fitness improves by the sealed minimum",
            "all changes remain local, reversible, and zero-egress",
            "canonical state is not mutated",
        ),
        "explicit_exclusions": (
            "merge",
            "deployment",
            "provider call",
            "financial action",
            "external communication",
        ),
        "exact_repository_revision": REVISION,
        "effect_ceiling": effect_ceiling,
        "risk_tier": "R1",
        "sealed": True,
    }
    payload.update(updates)
    return ObjectiveContract.model_validate(payload)


def request(
    current: EcosystemState,
    observed: TelemetrySnapshot | None = None,
    *,
    run_id: str = "ECO-RUN-REFERENCE-V1",
    mode: str = "LOCAL_SHADOW",
    previous: str | None = None,
    producer_id: str = "AGT-AUTOPOIETIC-SYNTHESIZER",
    verifier_id: str = "AGT-OMEGA-INDEPENDENT-VERIFIER",
    objective_contract: ObjectiveContract | None = None,
) -> CycleRequest:
    return CycleRequest(
        run_id=run_id,
        objective=objective_contract or objective(),
        state=current,
        telemetry=observed or telemetry(current),
        mode=mode,
        previous_receipt_sha256=previous,
        producer_id=producer_id,
        verifier_id=verifier_id,
    )


def kernel(*, policy: AutopoieticPolicy | None = None, templates=None) -> AutopoieticKernel:
    cfg = config()
    return AutopoieticKernel(
        policy=policy or cfg.policy,
        templates=templates or cfg.templates,
    )


def deployment_template() -> CandidateTemplate:
    return CandidateTemplate(
        template_id="ECO-TEMPLATE-DEPLOYMENT-TEST",
        deficit_class=DeficitClass.PORTABILITY,
        priority=0,
        description="Attempt a real deployment effect so the authority boundary can be tested.",
        effect_class=EffectClass.DEPLOYMENT,
        operations=(
            PatchOperation(
                operation_id="ECO-OP-DEPLOYMENT-TEST",
                kind=OperationKind.SET_ARTIFACT,
                target="deployment.target",
                value="production",
                effect_class=EffectClass.DEPLOYMENT,
                reversible=False,
                rollback_supported=False,
            ),
        ),
        metric_impacts=(MetricImpact(metric="portability", delta=0.30),),
        resource_estimate=ResourceUse(
            operations=1,
            compute_units=5,
            peak_memory_mb=32,
            output_bytes=1024,
        ),
        evidence_requirements=("deployment permit", "rollback evidence"),
    )


def test_config_defines_a_provider_independent_human_governed_ecosystem() -> None:
    cfg = config()
    assert len(cfg.planes) >= 12
    assert cfg.independence.required_proprietary_providers == ()
    assert {"x86_64-cpu", "arm64-cpu", "wasm-wasi"} <= set(
        cfg.independence.compute_targets
    )
    assert cfg.policy.network_egress_allowed is False
    assert cfg.policy.self_authority_allowed is False
    assert cfg.policy.self_merge_allowed is False
    assert cfg.policy.canonical_state_write_allowed is False
    assert set(cfg.policy.autonomous_effects) == {
        EffectClass.PURE,
        EffectClass.READ_LOCAL,
        EffectClass.WRITE_REVERSIBLE,
    }


def test_local_shadow_cycle_is_deterministic_and_promotes_only_reversible_state() -> None:
    current = state()
    req = request(current)
    first = kernel().run_cycle(req)
    second = kernel().run_cycle(req)

    assert first == second
    assert first.receipt.phase == "PROMOTED_SHADOW"
    assert first.receipt.terminal_status == "PASS"
    assert first.receipt.promoted_to_shadow is True
    assert first.receipt.external_action_performed is False
    assert first.receipt.canonical_state_mutated is False
    assert first.receipt.network_calls_performed == 0
    assert first.receipt.provider_calls_performed == 0
    assert first.receipt.processes_spawned == 0
    assert first.receipt.filesystem_writes_performed == 0
    assert first.state.adapter_bindings["compute.default"] == "local-cpu-reference"
    assert "CAP-SILICON-AGNOSTIC-REFERENCE-RUNTIME" in first.state.capabilities
    assert first.shadow_telemetry is not None
    assert first.shadow_telemetry.portability == 0.75
    assert first.receipt.verify_hash()


def test_receipt_validates_against_closed_json_schema() -> None:
    result = kernel().run_cycle(request(state()))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(
        result.receipt.model_dump(mode="json")
    )


def test_plan_only_mode_never_mutates_shadow_state() -> None:
    current = state()
    result = kernel().run_cycle(request(current, mode="PLAN_ONLY"))
    assert result.state == current
    assert result.receipt.phase == "VERIFIED"
    assert result.receipt.executed_in_shadow is False
    assert result.receipt.logical_shadow_mutations == 0
    assert result.receipt.resulting_state_sha256 == current.digest


def test_satisfied_fitness_returns_no_change_receipt() -> None:
    current = state()
    observed = telemetry(current, portability=0.95)
    result = kernel().run_cycle(request(current, observed))
    assert result.deficits == ()
    assert result.receipt.phase == "NO_CHANGE_REQUIRED"
    assert result.receipt.proposed is False


def test_emergency_stop_blocks_before_planning() -> None:
    current = state(emergency_stop_active=True)
    result = kernel().run_cycle(request(current, telemetry(current)))
    assert result.receipt.reason == "EMERGENCY_STOP_ACTIVE"
    assert result.receipt.phase == "BLOCKED"
    assert result.candidate is None


def test_stale_telemetry_and_stale_repository_revision_fail_closed() -> None:
    current = state()
    wrong_state = state(revision=9)
    stale = telemetry(current).model_copy(update={"state_sha256": wrong_state.digest})
    result = kernel().run_cycle(request(current, stale))
    assert result.receipt.reason == "TELEMETRY_STATE_HASH_MISMATCH"

    stale_revision_state = state(
        exact_repository_revision="0" * 40,
    )
    result = kernel().run_cycle(
        request(stale_revision_state, telemetry(stale_revision_state))
    )
    assert result.receipt.reason == "STALE_REPOSITORY_REVISION"


def test_deployment_effect_stops_at_operator_authority_boundary() -> None:
    current = state()
    objective_contract = objective(
        EffectClass.DEPLOYMENT,
        risk_tier="R4",
    )
    result = kernel(templates=(deployment_template(),)).run_cycle(
        request(current, objective_contract=objective_contract)
    )
    assert result.receipt.terminal_status == "AWAITING_OPERATOR"
    assert result.receipt.operator_action_required is True
    assert result.receipt.executed_in_shadow is False
    assert result.receipt.external_action_performed is False
    assert result.verification is not None
    assert any(
        gate.gate_id == "GATE-POLICY-EFFECT" and gate.result == GateResult.BLOCKED
        for gate in result.verification.gates
    )


def test_self_verification_is_rejected() -> None:
    current = state()
    result = kernel().run_cycle(
        request(
            current,
            producer_id="AGT-SAME",
            verifier_id="AGT-SAME",
        )
    )
    assert result.receipt.reason == "VERIFICATION_FAILED:GATE-INDEPENDENT-VERIFIER"
    assert result.verification is not None
    assert result.verification.independent is False


def test_budget_exhaustion_blocks_candidate_before_execution() -> None:
    cfg = config()
    expensive = cfg.templates[-2].model_copy(
        update={
            "resource_estimate": ResourceUse(
                operations=1,
                compute_units=cfg.policy.budget.maximum_compute_units + 1,
                peak_memory_mb=32,
                output_bytes=1024,
            )
        }
    )
    result = kernel(templates=(expensive,)).run_cycle(request(state()))
    assert result.receipt.reason == "VERIFICATION_FAILED:GATE-BUDGET"
    assert result.receipt.executed_in_shadow is False


def test_raw_secret_shaped_material_is_rejected() -> None:
    cfg = config()
    unsafe = cfg.templates[-2].model_copy(
        update={
            "operations": (
                PatchOperation(
                    operation_id="ECO-OP-SECRET-REJECTION",
                    kind=OperationKind.SET_ARTIFACT,
                    target="runtime.test_value",
                    value="sk-proj-for-tests-NOTAREALSECRET1234567890",
                    effect_class=EffectClass.WRITE_REVERSIBLE,
                    reversible=True,
                    rollback_supported=True,
                ),
            )
        }
    )
    result = kernel(templates=(unsafe,)).run_cycle(request(state()))
    assert result.receipt.reason == "VERIFICATION_FAILED:GATE-SECRETS"


def test_sandbox_rejects_idempotency_replay_and_stale_candidate() -> None:
    cfg = config()
    current = state()
    req = request(current)
    deficit = detect_deficits(req.telemetry, cfg.policy)[0]
    template = next(
        item for item in cfg.templates if item.deficit_class == deficit.classification
    )
    candidate = _build_candidate(req, deficit, template)
    sandbox = InMemorySandbox()
    next_state, _, _ = sandbox.apply(current, candidate, cfg.policy)
    assert next_state.revision == 1
    with pytest.raises(ValueError, match="already been consumed"):
        sandbox.apply(current, candidate, cfg.policy)

    fresh_sandbox = InMemorySandbox()
    with pytest.raises(ValueError, match="stale candidate parent state"):
        fresh_sandbox.apply(next_state, candidate, cfg.policy)


def test_receipt_ledger_rejects_replay_and_detects_tampering() -> None:
    engine = kernel()
    result = engine.run_cycle(request(state()))
    with pytest.raises(ValueError, match="replay"):
        engine.ledger.append(result.receipt)

    tampered = result.receipt.model_copy(update={"reason": "TAMPERED"})
    assert tampered.verify_hash() is False
    assert ReceiptLedger.verify_chain((tampered,)) is False


def test_receipt_chain_requires_exact_predecessor() -> None:
    engine = kernel()
    first = engine.run_cycle(request(state()))
    assert engine.ledger.last_sha256 == first.receipt.receipt_sha256

    observed = first.shadow_telemetry
    assert observed is not None
    second_req = request(
        first.state,
        observed,
        run_id="ECO-RUN-REFERENCE-V2",
        previous=first.receipt.receipt_sha256,
    )
    second = engine.run_cycle(second_req)
    assert second.receipt.previous_receipt_sha256 == first.receipt.receipt_sha256
    assert ReceiptLedger.verify_chain(engine.ledger.receipts)

    bad = request(
        first.state,
        observed,
        run_id="ECO-RUN-BAD-PREDECESSOR",
        previous="f" * 64,
    )
    with pytest.raises(ValueError, match="current receipt chain head"):
        engine.run_cycle(bad)


def test_invalid_operation_cycle_is_rejected_at_contract_boundary() -> None:
    cfg = config()
    source = cfg.templates[-2]
    op1 = source.operations[0].model_copy(
        update={
            "operation_id": "ECO-OP-CYCLE-A",
            "depends_on": ("ECO-OP-CYCLE-B",),
        }
    )
    op2 = source.operations[-1].model_copy(
        update={
            "operation_id": "ECO-OP-CYCLE-B",
            "depends_on": ("ECO-OP-CYCLE-A",),
        }
    )
    template = source.model_copy(update={"operations": (op1, op2)})
    current = state()
    req = request(current)
    deficit = detect_deficits(req.telemetry, cfg.policy)[0]
    with pytest.raises(ValidationError, match="contains a cycle"):
        _build_candidate(req, deficit, template)


def test_policy_must_classify_every_effect_exactly_once() -> None:
    payload = config().policy.model_dump(mode="python")
    payload["operator_required_effects"] = tuple(
        effect
        for effect in payload["operator_required_effects"]
        if effect != EffectClass.DEPLOYMENT
    )
    with pytest.raises(ValidationError, match="classify every effect"):
        AutopoieticPolicy.model_validate(payload)

    payload = config().policy.model_dump(mode="python")
    payload["prohibited_effects"] = (EffectClass.WRITE_REVERSIBLE,)
    with pytest.raises(ValidationError, match="must be disjoint"):
        AutopoieticPolicy.model_validate(payload)


def test_receipt_hash_changes_for_any_semantic_change() -> None:
    receipt = kernel().run_cycle(request(state())).receipt
    payload = receipt.model_dump(mode="json", exclude={"receipt_sha256"})
    original = canonical_sha256(payload)
    changed = deepcopy(payload)
    changed["logical_shadow_mutations"] += 1
    assert canonical_sha256(changed) != original
    assert original == receipt.receipt_sha256


def test_cycle_receipt_rejects_false_external_action_claim() -> None:
    receipt = kernel().run_cycle(request(state())).receipt
    payload = receipt.model_dump(mode="python")
    payload["external_action_performed"] = True
    with pytest.raises(ValidationError):
        CycleReceipt.model_validate(payload)


def test_fabric_router_selects_best_admissible_open_local_adapter_deterministically() -> None:
    from src.autopoiesis import (
        AdapterKind,
        AdapterManifest,
        FabricRegistry,
        WorkloadDemand,
        select_adapter,
    )

    registry = FabricRegistry(
        registry_id="FABRIC-LOCAL-REFERENCE-V1",
        revision=1,
        adapters=(
            AdapterManifest(
                adapter_id="ADAPTER-LOCAL-CPU-REFERENCE",
                kind=AdapterKind.MODEL,
                protocol="local-python-callable",
                implementation_version="1.0.0",
                capabilities=("text.generate", "text.embed"),
                supported_effects=(EffectClass.PURE, EffectClass.READ_LOCAL),
                hardware_targets=("x86_64-cpu", "arm64-cpu"),
                data_locality="LOCAL_ONLY",
                open_standard=True,
                proprietary_dependency=False,
                quality_score=0.86,
                portability_score=0.98,
                estimated_latency_ms=80.0,
                estimated_cost_units=0.05,
                health_score=1.0,
                evidence_refs=("test://adapter/local-cpu",),
            ),
            AdapterManifest(
                adapter_id="ADAPTER-REMOTE-PROPRIETARY",
                kind=AdapterKind.MODEL,
                protocol="vendor-http",
                implementation_version="1.0.0",
                capabilities=("text.generate",),
                supported_effects=(EffectClass.READ_EXTERNAL,),
                hardware_targets=("remote-unknown",),
                data_locality="REMOTE_ONLY",
                open_standard=False,
                proprietary_dependency=True,
                quality_score=0.99,
                portability_score=0.10,
                estimated_latency_ms=20.0,
                estimated_cost_units=0.01,
                health_score=1.0,
                evidence_refs=("test://adapter/remote",),
            ),
        ),
    )
    demand = WorkloadDemand(
        workload_id="WORKLOAD-TEXT-LOCAL-V1",
        kind=AdapterKind.MODEL,
        required_capabilities=("text.generate",),
        required_effect=EffectClass.PURE,
        allowed_hardware_targets=("x86_64-cpu",),
        local_only=True,
        open_standard_required=True,
        proprietary_dependency_allowed=False,
        minimum_quality=0.80,
        minimum_portability=0.80,
        minimum_health=0.90,
    )

    first = select_adapter(registry, demand)
    second = select_adapter(registry, demand)
    assert first == second
    assert first.selected_adapter_id == "ADAPTER-LOCAL-CPU-REFERENCE"
    assert first.vendor_identity_used_as_score is False
    rejected = {item.adapter_id: item.reasons for item in first.rejected}
    assert "LOCALITY_VIOLATION" in rejected["ADAPTER-REMOTE-PROPRIETARY"]
    assert "PROPRIETARY_DEPENDENCY_DENIED" in rejected["ADAPTER-REMOTE-PROPRIETARY"]


def test_fabric_router_fails_closed_when_no_adapter_satisfies_hard_gates() -> None:
    from src.autopoiesis import (
        AdapterKind,
        AdapterManifest,
        FabricRegistry,
        WorkloadDemand,
        select_adapter,
    )

    registry = FabricRegistry(
        registry_id="FABRIC-NO-MATCH-V1",
        revision=1,
        adapters=(
            AdapterManifest(
                adapter_id="ADAPTER-LOCAL-TEXT-ONLY",
                kind=AdapterKind.MODEL,
                protocol="local-python-callable",
                implementation_version="1.0.0",
                capabilities=("text.generate",),
                supported_effects=(EffectClass.PURE,),
                hardware_targets=("x86_64-cpu",),
                data_locality="LOCAL_ONLY",
                open_standard=True,
                proprietary_dependency=False,
                quality_score=0.9,
                portability_score=0.9,
                estimated_latency_ms=25.0,
                estimated_cost_units=0.0,
                health_score=1.0,
                evidence_refs=("test://adapter/text-only",),
            ),
        ),
    )
    demand = WorkloadDemand(
        workload_id="WORKLOAD-VIDEO-LOCAL-V1",
        kind=AdapterKind.MODEL,
        required_capabilities=("video.generate",),
        required_effect=EffectClass.PURE,
    )
    decision = select_adapter(registry, demand)
    assert decision.terminal_status == "NO_ADMISSIBLE_ADAPTER"
    assert decision.selected_adapter_id is None
    assert decision.score_by_adapter == {}
    assert "MISSING_CAPABILITIES:video.generate" in decision.rejected[0].reasons



def test_committed_fabric_and_request_artifacts_validate_against_schemas() -> None:
    from src.autopoiesis import CycleRequest, load_fabric_registry

    fabric_path = ROOT / "config" / "aigc_adapter_fabric.v1.json"
    request_path = ROOT / "config" / "aigc_autopoietic_local_cycle.example.json"
    fabric_schema_path = ROOT / "schemas" / "aigc_adapter_fabric.schema.json"
    request_schema_path = ROOT / "schemas" / "aigc_autopoietic_cycle_request.schema.json"
    ecosystem_schema_path = ROOT / "schemas" / "aigc_autopoietic_ecosystem.schema.json"

    fabric = load_fabric_registry(fabric_path)
    reference_request = CycleRequest.model_validate_json(
        request_path.read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(
        json.loads(fabric_schema_path.read_text(encoding="utf-8"))
    ).validate(fabric.model_dump(mode="json"))
    jsonschema.Draft202012Validator(
        json.loads(request_schema_path.read_text(encoding="utf-8"))
    ).validate(reference_request.model_dump(mode="json", exclude_computed_fields=True))
    jsonschema.Draft202012Validator(
        json.loads(ecosystem_schema_path.read_text(encoding="utf-8"))
    ).validate(config().model_dump(mode="json"))


def test_reference_cli_runs_end_to_end_without_external_effects() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_autopoietic_cycle.py")],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    receipt = payload["receipt"]
    assert receipt["terminal_status"] == "PASS"
    assert receipt["phase"] == "PROMOTED_SHADOW"
    assert receipt["canonical_state_mutated"] is False
    assert receipt["external_action_performed"] is False
    assert receipt["network_calls_performed"] == 0
    assert receipt["provider_calls_performed"] == 0
    assert receipt["processes_spawned"] == 0
    assert receipt["secrets_accessed"] == 0



def test_randomized_local_cycles_preserve_determinism_and_zero_external_effects() -> None:
    rng = random.Random(1666)
    cfg = config()
    for index in range(100):
        current = state()
        observed = TelemetrySnapshot(
            telemetry_id=f"TELEM-FUZZ-{index:03d}",
            source=TelemetrySource.OBSERVED_LOCAL,
            observed_epoch=index + 1,
            state_sha256=current.digest,
            source_revision=REVISION,
            quality=rng.random(),
            throughput=rng.random() * 2.0,
            latency_ms=rng.random() * 2_000.0,
            error_rate=rng.random() * 0.10,
            drift=rng.random() * 0.20,
            cost_units=rng.random() * 2.0,
            security_findings=rng.randint(0, 3),
            portability=rng.random(),
            evidence_refs=(f"fuzz://telemetry/{index}",),
        )
        req = request(
            current,
            observed,
            run_id=f"ECO-RUN-FUZZ-{index:03d}",
        )
        first = AutopoieticKernel(policy=cfg.policy, templates=cfg.templates).run_cycle(req)
        second = AutopoieticKernel(policy=cfg.policy, templates=cfg.templates).run_cycle(req)
        assert first == second
        assert first.receipt.verify_hash()
        assert first.receipt.canonical_state_mutated is False
        assert first.receipt.external_action_performed is False
        assert first.receipt.network_calls_performed == 0
        assert first.receipt.provider_calls_performed == 0
        assert first.receipt.processes_spawned == 0
        assert first.receipt.secrets_accessed == 0
