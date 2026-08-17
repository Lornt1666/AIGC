from __future__ import annotations

import json
from pathlib import Path

from src.core.nexus.evidence_program import build_evidence_program


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/aigc_universal_integration_registry.v1.json"


def _requests_by_gate() -> dict[str, dict[str, object]]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    _, request_bundle = build_evidence_program(registry, ROOT)
    return {item["gate_id"]: item for item in request_bundle["requests"]}


def test_exact_head_ci_does_not_require_deployment_or_public_traffic_authority():
    request = _requests_by_gate()["surface.nexus_linux_server.exact_head_ci"]
    assert request["required_authority"] == []


def test_deployed_web_origin_retains_consequential_authority_requirements():
    request = _requests_by_gate()["surface.nexus_web.deployed_url"]
    assert request["required_authority"] == [
        "cloud_mutation_authorized",
        "public_traffic_authorized",
    ]
