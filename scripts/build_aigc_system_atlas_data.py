from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.epistemic.canonicalization import canonical_sha256
from src.integrations.mcp.server import build_mcp_server


def _load(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def build_atlas_data() -> dict[str, object]:
    registry = _load("config/aigc_universal_integration_registry.v1.json")
    readiness = _load("reports/artifacts/aigc_universal_readiness_local_validation.json")
    apex = _load("config/aigc_omniproj_apex_v2.json")
    subsystem_contracts = _load("config/aigc_subsystem_contracts.v1.json")
    wealth = _load("config/aigc_wealth_operator_policy.v1.json")
    seed = _load("config/regenexcalibur_universe_seed.v1.json")
    llm = _load("config/aigc_llm_stack.v1.json")
    mcp_tools = asyncio.run(build_mcp_server().list_tools())

    parameter_types = Counter(item["variable_type"] for item in apex["parameters"])
    surface_states = Counter(item["status"] for item in registry["surfaces"])
    wealth_states = Counter(
        "approval_gated" if item["approval_required"] else "policy_path"
        for item in wealth["actions"]
    )
    payload: dict[str, object] = {
        "schema_version": "aigc.system-atlas-snapshot.v1",
        "evidence_scope": "LOCAL_CANDIDATE_NOT_EXACT_HEAD_CI",
        "identity": {
            "name": apex["project"]["name"],
            "owner": apex["project"]["owner"],
            "current_state": apex["project"]["current_state"],
            "target_state": apex["project"]["target_state"],
            "product_definition": apex["project"]["domain"],
        },
        "portfolio": {
            "integrated_subsystems": len(registry["subsystems"]),
            "delivery_surfaces": len(registry["surfaces"]),
            "connectors": len(registry["connectors"]),
            "occupation_packs": len(list((ROOT / "config" / "occupation_packs").glob("*.json"))),
            "wealth_actions": len(wealth["actions"]),
            "mcp_tools": len(mcp_tools),
            "life_domains": len(seed["life_domains"]),
            "regenexcalibur_agent_roles": 8,
            "llm_training_cost_cad": llm["resources"]["maximum_training_cost_cad"],
            "llm_gpu_hours": llm["resources"]["maximum_gpu_hours"],
        },
        "readiness": {
            "applicable_required_checks": readiness["applicable_required_checks"],
            "verified_required_checks": readiness["verified_required_checks"],
            "unverified_required_checks": readiness["applicable_required_checks"]
            - readiness["verified_required_checks"],
            "verified_applicable_ratio": readiness["verified_applicable_ratio"],
            "minimum_release_ratio": registry["completion_policy"][
                "minimum_verified_applicable_ratio"
            ],
            "production_ready": readiness["production_ready"],
            "authority_granted": readiness["authority_granted"],
            "external_action_performed": readiness["external_action_performed"],
            "blockers": readiness["blockers"],
        },
        "conceptual_model": {
            key: len(apex[key])
            for key in (
                "entities",
                "relationships",
                "states",
                "transitions",
                "methodology_stack",
                "heuristics",
                "parameters",
                "actions",
                "decisions",
                "risks",
                "constraints",
                "connectors",
                "external_blockers",
                "sources",
            )
        },
        "parametric_profile": dict(sorted(parameter_types.items())),
        "surface_status": dict(sorted(surface_states.items())),
        "wealth_action_profile": dict(sorted(wealth_states.items())),
        "subsystems": [
            {
                "id": subsystem["id"],
                "name": subsystem["name"],
                "purpose": next(
                    item["purpose"]
                    for item in registry["subsystems"]
                    if item["id"] == subsystem["id"]
                ),
                "contract_count": len(subsystem["contracts"]),
            }
            for subsystem in subsystem_contracts["subsystems"]
        ],
        "surfaces": [
            {
                "id": surface["id"],
                "required_for_v1": surface["required_for_v1"],
                "status": surface["status"],
                "required_evidence_count": len(surface["required_evidence"]),
                "verified_evidence_count": len(surface["evidence_receipts"]),
                "blocker_count": len(surface["blockers"]),
            }
            for surface in registry["surfaces"]
        ],
        "methodologies": [
            {
                "id": item["id"],
                "name": item["name"],
                "fit_score": item["fit_score"],
                "problem": item["problem"],
            }
            for item in apex["methodology_stack"]
        ],
        "parameters": [
            {
                "id": item["id"],
                "name": item["name"],
                "symbol": item["symbol"],
                "type": item["variable_type"],
                "target": item["target"],
                "meaning": item["definition"],
            }
            for item in apex["parameters"]
        ],
    }
    payload["snapshot_sha256"] = canonical_sha256(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the canonical AIGC atlas data")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed atlas snapshot differs from canonical inputs",
    )
    args = parser.parse_args()
    payload = build_atlas_data()
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.check:
        target = args.output or (
            ROOT / "reports" / "artifacts" / "aigc_system_atlas_local_snapshot.json"
        )
        if not target.is_file() or target.read_text(encoding="utf-8") != serialized:
            print(
                f"Atlas snapshot is stale: {target}. Regenerate it with --output.",
                file=sys.stderr,
            )
            return 1
        print(f"Atlas snapshot is current: {target}")
        return 0
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
