from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.autopoiesis import (
    AdapterKind,
    AutopoieticKernel,
    CandidateTemplate,
    CycleRequest,
    DeficitClass,
    EcosystemState,
    EffectClass,
    MetricImpact,
    ObjectiveContract,
    OperationKind,
    PatchOperation,
    ReceiptLedger,
    ResourceUse,
    TelemetrySnapshot,
    TelemetrySource,
    canonical_sha256,
    WorkloadDemand,
    config_sha256,
    load_ecosystem_config,
    load_fabric_registry,
    select_adapter,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "aigc_autopoietic_ecosystem.v1.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "aigc_autopoietic_cycle_receipt.schema.json"
DEFAULT_CONFIG_SCHEMA = ROOT / "schemas" / "aigc_autopoietic_ecosystem.schema.json"
DEFAULT_FABRIC = ROOT / "config" / "aigc_adapter_fabric.v1.json"
DEFAULT_FABRIC_SCHEMA = ROOT / "schemas" / "aigc_adapter_fabric.schema.json"
DEFAULT_REQUEST = ROOT / "config" / "aigc_autopoietic_local_cycle.example.json"
DEFAULT_REQUEST_SCHEMA = ROOT / "schemas" / "aigc_autopoietic_cycle_request.schema.json"
DEFAULT_OUTPUT = ROOT / "reports" / "artifacts" / "aigc_autopoietic_local_validation.json"
DEFAULT_REVISION = "2a9c039e41a7d9db8410120614cde044ca785e0f"


def _state(revision: str, *, emergency_stop: bool = False) -> EcosystemState:
    return EcosystemState(
        state_id="ECO-STATE-LOCAL-VALIDATION",
        revision=0,
        exact_repository_revision=revision,
        artifacts={"runtime.mode": "local-shadow"},
        capabilities=(),
        adapter_bindings={},
        emergency_stop_active=emergency_stop,
    )


def _telemetry(state: EcosystemState) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        telemetry_id="TELEM-LOCAL-VALIDATION",
        source=TelemetrySource.OBSERVED_LOCAL,
        observed_epoch=1,
        state_sha256=state.digest,
        source_revision=state.exact_repository_revision,
        quality=0.90,
        throughput=1.20,
        latency_ms=200.0,
        error_rate=0.01,
        drift=0.02,
        cost_units=0.50,
        security_findings=0,
        portability=0.50,
        evidence_refs=("local://validation/telemetry",),
    )


def _objective(revision: str, effect_ceiling: EffectClass) -> ObjectiveContract:
    return ObjectiveContract(
        objective_id="OBJ-LOCAL-VALIDATION",
        revision=1,
        objective="Validate one deterministic and reversible local AIGC autopoietic cycle.",
        target_component="AIGC_AUTOPOIETIC_CONTROL_SPINE",
        acceptance_criteria=(
            "receipt hash verifies",
            "receipt schema validates",
            "local shadow fitness improves",
            "external action counters remain zero",
        ),
        explicit_exclusions=("merge", "deployment", "provider call", "financial action"),
        exact_repository_revision=revision,
        effect_ceiling=effect_ceiling,
        risk_tier="R1" if effect_ceiling == EffectClass.WRITE_REVERSIBLE else "R4",
        sealed=True,
    )


def _request(
    state: EcosystemState,
    *,
    run_id: str,
    effect_ceiling: EffectClass = EffectClass.WRITE_REVERSIBLE,
    previous: str | None = None,
) -> CycleRequest:
    return CycleRequest(
        run_id=run_id,
        objective=_objective(state.exact_repository_revision, effect_ceiling),
        state=state,
        telemetry=_telemetry(state),
        previous_receipt_sha256=previous,
        mode="LOCAL_SHADOW",
    )


def _deployment_template() -> CandidateTemplate:
    return CandidateTemplate(
        template_id="ECO-TEMPLATE-VALIDATION-DEPLOYMENT",
        deficit_class=DeficitClass.PORTABILITY,
        priority=0,
        description="Validation-only deployment request that must stop at operator authority.",
        effect_class=EffectClass.DEPLOYMENT,
        operations=(
            PatchOperation(
                operation_id="ECO-OP-VALIDATION-DEPLOYMENT",
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
        evidence_requirements=("operator permit", "deployment receipt"),
    )


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "result": "PASS" if passed else "FAIL", "detail": detail}


def run_validation(
    config_path: Path,
    schema_path: Path,
    revision: str,
    *,
    config_schema_path: Path = DEFAULT_CONFIG_SCHEMA,
    fabric_path: Path = DEFAULT_FABRIC,
    fabric_schema_path: Path = DEFAULT_FABRIC_SCHEMA,
    request_path: Path = DEFAULT_REQUEST,
    request_schema_path: Path = DEFAULT_REQUEST_SCHEMA,
) -> dict[str, Any]:
    cfg = load_ecosystem_config(config_path)
    fabric = load_fabric_registry(fabric_path)
    reference_request = CycleRequest.model_validate_json(
        request_path.read_text(encoding="utf-8")
    )

    Draft202012Validator(
        json.loads(config_schema_path.read_text(encoding="utf-8"))
    ).validate(cfg.model_dump(mode="json"))
    Draft202012Validator(
        json.loads(fabric_schema_path.read_text(encoding="utf-8"))
    ).validate(fabric.model_dump(mode="json"))
    Draft202012Validator(
        json.loads(request_schema_path.read_text(encoding="utf-8"))
    ).validate(reference_request.model_dump(mode="json", exclude_computed_fields=True))
    initial = _state(revision)
    first_engine = AutopoieticKernel(policy=cfg.policy, templates=cfg.templates)
    first = first_engine.run_cycle(_request(initial, run_id="ECO-RUN-LOCAL-VALIDATION-A"))
    second = AutopoieticKernel(policy=cfg.policy, templates=cfg.templates).run_cycle(
        _request(initial, run_id="ECO-RUN-LOCAL-VALIDATION-A")
    )

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(first.receipt.model_dump(mode="json"))

    stopped = _state(revision, emergency_stop=True)
    stopped_result = AutopoieticKernel(
        policy=cfg.policy, templates=cfg.templates
    ).run_cycle(_request(stopped, run_id="ECO-RUN-LOCAL-KILL-SWITCH"))

    external = AutopoieticKernel(
        policy=cfg.policy, templates=(_deployment_template(),)
    ).run_cycle(
        _request(
            initial,
            run_id="ECO-RUN-LOCAL-DEPLOYMENT-BOUNDARY",
            effect_ceiling=EffectClass.DEPLOYMENT,
        )
    )

    tampered = first.receipt.model_copy(update={"reason": "TAMPERED"})

    routing_demand = WorkloadDemand(
        workload_id="WORKLOAD-VALIDATE-LOCAL-TEXT-V1",
        kind=AdapterKind.MODEL,
        required_capabilities=("text.generate",),
        required_effect=EffectClass.PURE,
        allowed_hardware_targets=("x86_64-cpu", "arm64-cpu"),
        local_only=True,
        open_standard_required=True,
        proprietary_dependency_allowed=False,
        minimum_quality=0.80,
        minimum_portability=0.80,
        minimum_health=0.90,
    )
    route_first = select_adapter(fabric, routing_demand)
    route_second = select_adapter(fabric, routing_demand)

    checks = [
        _check(
            "config_valid",
            True,
            "closed Pydantic ecosystem configuration and Draft 2020-12 schema loaded",
        ),
        _check(
            "fabric_registry_valid",
            len(fabric.adapters) >= 6,
            "provider-neutral model, compute, storage, orchestration, modality, and tool adapters loaded",
        ),
        _check(
            "reference_request_valid",
            reference_request.objective.exact_repository_revision == revision,
            "reference cycle request validates and binds the exact inspected repository revision",
        ),
        _check(
            "provider_independence",
            cfg.independence.required_proprietary_providers == (),
            "no proprietary provider is required by the sovereign profile",
        ),
        _check(
            "deterministic_adapter_routing",
            route_first == route_second
            and route_first.selected_adapter_id == "ADAPTER-MODEL-LOCAL-CPU-REFERENCE"
            and route_first.vendor_identity_used_as_score is False,
            "hard capability gates select the open local reference adapter reproducibly",
        ),
        _check(
            "deterministic_replay",
            first == second,
            "fresh kernels produced byte-equivalent model results for the same request",
        ),
        _check(
            "shadow_promotion",
            first.receipt.promoted_to_shadow and first.state.revision == 1,
            "one reversible local shadow improvement was promoted",
        ),
        _check(
            "zero_external_effects",
            all(
                (
                    first.receipt.external_action_performed is False,
                    first.receipt.network_calls_performed == 0,
                    first.receipt.provider_calls_performed == 0,
                    first.receipt.processes_spawned == 0,
                    first.receipt.filesystem_writes_performed == 0,
                    first.receipt.secrets_accessed == 0,
                    first.receipt.canonical_state_mutated is False,
                )
            ),
            "all external and canonical mutation counters remain zero",
        ),
        _check("receipt_hash", first.receipt.verify_hash(), "canonical receipt hash verifies"),
        _check("receipt_schema", True, "Draft 2020-12 receipt schema validation passed"),
        _check(
            "kill_switch",
            stopped_result.receipt.reason == "EMERGENCY_STOP_ACTIVE",
            "emergency stop blocks before formulation",
        ),
        _check(
            "operator_authority_boundary",
            external.receipt.operator_action_required
            and external.receipt.executed_in_shadow is False,
            "deployment effect stopped at fresh operator authority boundary",
        ),
        _check(
            "tamper_detection",
            tampered.verify_hash() is False
            and ReceiptLedger.verify_chain((tampered,)) is False,
            "semantic receipt modification invalidates the hash chain",
        ),
    ]
    passed = sum(item["result"] == "PASS" for item in checks)
    report: dict[str, Any] = {
        "schema_version": "aigc.autopoietic-local-validation.v1",
        "validation_id": "AIGC-AUTOPOIETIC-LOCAL-" + canonical_sha256(
            {
                "revision": revision,
                "config_sha256": config_sha256(cfg),
                "receipt_sha256": first.receipt.receipt_sha256,
            }
        )[:24].upper(),
        "exact_repository_revision": revision,
        "config_sha256": config_sha256(cfg),
        "fabric_sha256": fabric.digest,
        "routing_decision_sha256": route_first.digest,
        "receipt_sha256": first.receipt.receipt_sha256,
        "checks": checks,
        "checks_passed": passed,
        "checks_failed": len(checks) - passed,
        "all_checks_passed": passed == len(checks),
        "local_shadow_revision": first.state.revision,
        "external_action_performed": False,
        "canonical_state_mutated": False,
        "network_calls_performed": 0,
        "provider_calls_performed": 0,
        "processes_spawned": 0,
        "filesystem_writes_performed": 0,
        "secrets_accessed": 0,
        "merge_performed": False,
        "deployment_performed": False,
        "production_ready": False,
        "self_hosting_proven": False,
        "superintelligence_claimed": False,
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--config-schema", type=Path, default=DEFAULT_CONFIG_SCHEMA)
    parser.add_argument("--fabric", type=Path, default=DEFAULT_FABRIC)
    parser.add_argument("--fabric-schema", type=Path, default=DEFAULT_FABRIC_SCHEMA)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--request-schema", type=Path, default=DEFAULT_REQUEST_SCHEMA)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run_validation(
        args.config,
        args.schema,
        args.revision,
        config_schema_path=args.config_schema,
        fabric_path=args.fabric,
        fabric_schema_path=args.fabric_schema,
        request_path=args.request,
        request_schema_path=args.request_schema,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
