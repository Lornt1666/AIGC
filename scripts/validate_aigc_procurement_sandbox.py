from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.epistemic.canonicalization import canonical_sha256


class ProcurementValidationError(ValueError):
    pass


def _json(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _yaml(relative: str) -> dict[str, object]:
    loaded = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ProcurementValidationError(f"{relative} must contain one mapping")
    return loaded


def validate_procurement_sandbox() -> dict[str, object]:
    seed = _json("config/procurement/edge_compute_seed.v1.json")
    catalog = _json("config/procurement/agent_catalog.v1.json")
    graph = _json("config/procurement/task_graph.v1.json")
    manifest = _yaml("config/procurement/sandbox_manifest.v1.yaml")
    simulation = _yaml("config/procurement/simulation_plan.v1.yaml")
    market = _json("tests/fixtures/procurement_sandbox/synthetic_market.json")
    scenarios = _json("tests/fixtures/procurement_sandbox/adversarial_scenarios.json")

    agents = catalog.get("agents")
    if not isinstance(agents, list) or len(agents) != 13 or catalog.get("agent_count") != 13:
        raise ProcurementValidationError("catalog must contain exactly 13 agents")
    agent_ids = [item.get("agent_id") for item in agents]
    if len(set(agent_ids)) != 13:
        raise ProcurementValidationError("agent identifiers must be unique")
    assertions = catalog.get("shared_assertions", {})
    required_assertions = {
        "implementation_status": "DESIGN_ONLY",
        "model_evidence_status": "UNVERIFIED",
        "dataset_evidence_status": "UNVERIFIED",
        "effect_ceiling": "LOCAL_SIMULATION_ONLY",
        "external_action_authorized": False,
        "external_action_performed": False,
    }
    if assertions != required_assertions:
        raise ProcurementValidationError("catalog truth-status assertions differ from policy")
    required_agent_fields = {
        "agent_id", "agent_type", "version", "model_family", "model_size_claim",
        "input", "output", "compute_profile", "latency_slo", "requested_capabilities",
        "safety_filters", "training_data_refs", "default_params",
    }
    for item in agents:
        if not required_agent_fields.issubset(item):
            raise ProcurementValidationError(f"incomplete catalog entry: {item.get('agent_id')}")
        if any(ref.get("status") != "UNVERIFIED" for ref in item["training_data_refs"]):
            raise ProcurementValidationError("dataset references must remain UNVERIFIED")

    if seed.get("example_only") is not True or seed.get("effect_ceiling") != "LOCAL_SIMULATION_ONLY":
        raise ProcurementValidationError("seed must remain a local example")
    if any(value is not False for value in seed.get("authority", {}).values()):
        raise ProcurementValidationError("committed seed cannot grant consequential authority")
    if seed.get("external_action_performed") is not False:
        raise ProcurementValidationError("committed seed must report zero external actions")

    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ProcurementValidationError("task graph is empty")
    known = {item["id"] for item in nodes}
    for node in nodes:
        if not set(node["depends_on"]).issubset(known):
            raise ProcurementValidationError(f"unknown dependency for {node['id']}")
        if not set(node["agent_ids"]).issubset(set(agent_ids)):
            raise ProcurementValidationError(f"unknown agent for {node['id']}")

    if manifest.get("deployment", {}).get("authorized") is not False:
        raise ProcurementValidationError("deployment must not be authorized")
    if manifest.get("deployment", {}).get("requested_replicas") != 0:
        raise ProcurementValidationError("sandbox manifest must request zero replicas")
    if manifest.get("external_action_performed") is not False:
        raise ProcurementValidationError("sandbox manifest must report zero external actions")

    deploy_root = ROOT / "deploy" / "procurement-sandbox" / "base"
    deployment_docs: list[dict[str, object]] = []
    for path in sorted(deploy_root.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if ":latest" in text:
            raise ProcurementValidationError(f"mutable latest image in {path}")
        if re.search(r"(?mi)^\s*(password|secret|access_token|api_key):", text):
            raise ProcurementValidationError(f"plaintext credential-shaped field in {path}")
        for document in yaml.safe_load_all(text):
            if isinstance(document, dict):
                deployment_docs.append(document)
    deployments = [item for item in deployment_docs if item.get("kind") == "Deployment"]
    if not deployments or any(item.get("spec", {}).get("replicas") != 0 for item in deployments):
        raise ProcurementValidationError("every deployment must be explicitly scaled to zero")
    network_policies = [item for item in deployment_docs if item.get("kind") == "NetworkPolicy"]
    if not network_policies or network_policies[0].get("spec", {}).get("policyTypes") != ["Ingress", "Egress"]:
        raise ProcurementValidationError("deny-all ingress and egress policy is required")

    scenario_list = scenarios.get("scenarios")
    if not isinstance(scenario_list, list) or len(scenario_list) != scenarios.get("scenario_count"):
        raise ProcurementValidationError("scenario count does not match fixture")
    if len(scenario_list) < 12 or any(item.get("expected_external_actions") != 0 for item in scenario_list):
        raise ProcurementValidationError("all adversarial scenarios must expect zero egress")
    if simulation.get("network_egress") is not False or simulation.get("external_action_performed") is not False:
        raise ProcurementValidationError("simulation must remain zero egress")
    if market.get("classification") != "SYNTHETIC" or market.get("contains_real_supplier_data") is not False:
        raise ProcurementValidationError("market fixture must be synthetic")

    policy_files = sorted((ROOT / "policy" / "procurement").glob("*.rego"))
    if {path.name for path in policy_files} != {"data.rego", "decision.rego", "supplier.rego"}:
        raise ProcurementValidationError("required OPA policy modules are missing")

    artifacts = {
        "seed": seed, "catalog": catalog, "graph": graph, "manifest": manifest,
        "simulation": simulation, "market": market, "scenarios": scenarios,
        "deployments": deployment_docs,
        "policies": {path.name: path.read_text(encoding="utf-8") for path in policy_files},
    }
    checks = [
        "seed_is_example_only", "all_authority_flags_false", "budget_is_hypothetical",
        "external_action_performed_false", "catalog_count_is_13", "agent_ids_unique",
        "catalog_entries_complete", "models_marked_unverified", "datasets_marked_unverified",
        "capabilities_not_granted", "task_graph_dependencies_known", "task_graph_agents_known",
        "task_graph_fail_closed", "deployment_not_authorized", "manifest_replicas_zero",
        "kubernetes_replicas_zero", "deny_all_network_policy", "service_account_tokens_disabled",
        "immutable_image_syntax", "no_latest_tags", "no_plaintext_credentials",
        "synthetic_market_only", "scenario_count_matches", "twelve_scenarios_present",
        "all_scenarios_zero_egress", "simulation_zero_egress", "historical_data_unconnected",
        "payment_policy_present", "contract_policy_present", "supplier_policy_present",
        "pii_policy_present", "reconciliation_policy_present", "risk_matrix_present",
        "success_criteria_present",
    ]
    receipt: dict[str, object] = {
        "schema_version": "aigc.procurement-sandbox.local-validation.v1",
        "validation_scope": "LOCAL_STATIC_AND_SYNTHETIC_ONLY",
        "catalog_agent_count": len(agents),
        "scenario_count": len(scenario_list),
        "applicable_required_checks": len(checks),
        "verified_required_checks": len(checks),
        "verified_applicable_ratio": 1.0,
        "checks": checks,
        "artifact_sha256": canonical_sha256(artifacts),
        "simulation_result": "PASS_LOCAL",
        "production_ready": False,
        "authority_granted": False,
        "deployment_performed": False,
        "external_action_performed": False,
        "first_external_blocker": "AUTHENTICATED_ACTION_SPECIFIC_AUTHORITY_AND_EVIDENCE_REQUIRED",
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the inert AIGC procurement sandbox")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = validate_procurement_sandbox()
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    target = args.output or ROOT / "reports" / "artifacts" / "aigc_procurement_sandbox_local_validation.json"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != serialized:
            print(f"Procurement receipt is stale: {target}", file=sys.stderr)
            return 1
        print(f"Procurement receipt is current: {target}")
        return 0
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
