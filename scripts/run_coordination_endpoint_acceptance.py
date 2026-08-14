from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.epistemic.canonicalization import canonical_sha256
from src.webapp.regenexcalibur_api import create_regenexcalibur_app


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the deterministic AIGC coordination engineering endpoint"
    )
    parser.add_argument(
        "--request",
        type=Path,
        default=ROOT / "config" / "aigc_coordination_example.v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "reports"
        / "artifacts"
        / "aigc_coordination_endpoint_local_validation.json",
    )
    args = parser.parse_args()

    request = json.loads(args.request.read_text(encoding="utf-8"))
    client = TestClient(create_regenexcalibur_app())
    first = client.post("/v1/coordination/engineer", json=request)
    second = client.post("/v1/coordination/engineer", json=request)

    execution_request = deepcopy(request)
    execution_request["execution_requested"] = True
    execution = client.post("/v1/coordination/engineer", json=execution_request)

    secret_request = deepcopy(request)
    secret_request["tools"][0]["parameters"] = {"token": "must-not-be-accepted"}
    secret = client.post("/v1/coordination/engineer", json=secret_request)

    cycle_request = deepcopy(request)
    cycle_request["agents"][0]["depends_on_agent_ids"] = ["AGT-VERIFIER"]
    cycle = client.post("/v1/coordination/engineer", json=cycle_request)

    response = first.json() if first.status_code == 200 else {}
    checks = {
        "happy_path_http_200": first.status_code == 200,
        "deterministic_response": first.json() == second.json(),
        "closed_openapi_request_schema": (
            client.get("/openapi.json")
            .json()["components"]["schemas"]["CoordinationEngineeringRequest"]
            .get("additionalProperties")
            is False
        ),
        "state_projection_hides_values": "values" not in response.get("state", {}),
        "acyclic_waves_emitted": bool(
            response.get("multi_agent_coordination", {}).get("waves")
        ),
        "alpha_plan_embedded": response.get("alpha_plan", {}).get("alpha_plan_version")
        == "aigc.alpha-plan.v1",
        "execution_request_blocked": execution.status_code == 200
        and execution.json().get("verification", {}).get("first_blocker")
        == "ENDPOINT_PLAN_ONLY",
        "secret_input_rejected": secret.status_code == 422,
        "cyclic_graph_rejected": cycle.status_code == 422,
        "zero_egress_receipt": response.get("zero_egress") is True
        and response.get("provider_calls_performed") == 0
        and response.get("tool_dispatches_performed") == 0
        and response.get("processes_spawned") == 0
        and response.get("memory_writes_performed") == 0
        and response.get("external_actions_performed") == 0,
        "no_authority_granted": response.get("authority_granted") is False,
    }
    passed = sum(checks.values())
    evidence = {
        "schema_version": "aigc.coordination-endpoint-validation.v1",
        "scope": "LOCAL_ZERO_EGRESS",
        "endpoint": "POST /v1/coordination/engineer",
        "request_fixture": str(args.request.relative_to(ROOT)),
        "request_sha256": canonical_sha256(request),
        "coordination_receipt_sha256": response.get("receipt_sha256"),
        "checks": checks,
        "verified_checks": passed,
        "applicable_checks": len(checks),
        "verified_ratio": passed / len(checks),
        "terminal_status": "PASS" if passed == len(checks) else "FAILED_SAFE",
        "production_ready": False,
        "authority_granted": False,
        "external_actions_performed": 0,
    }
    evidence["evidence_sha256"] = canonical_sha256(evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"{evidence['terminal_status']} {passed}/{len(checks)} "
        f"{evidence['evidence_sha256']}"
    )
    return 0 if evidence["terminal_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
