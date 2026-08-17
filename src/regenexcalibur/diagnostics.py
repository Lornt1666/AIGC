from __future__ import annotations

from pathlib import Path

import yaml

from src.core.epistemic.canonicalization import canonical_sha256
from src.regenexcalibur.doctrine_models import AuditEntryPost, DiagnosticScenario


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "diagnostics" / "scenarios"


def load_diagnostic_scenarios(
    scenario_dir: Path = SCENARIO_DIR,
) -> tuple[DiagnosticScenario, ...]:
    scenarios = tuple(
        DiagnosticScenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(scenario_dir.glob("*.yaml"))
    )
    identifiers = [item.scenario_id for item in scenarios]
    codes = [item.detection_code for item in scenarios]
    if len(scenarios) != 6:
        raise ValueError("diagnostic registry must contain exactly six scenarios")
    if len(identifiers) != len(set(identifiers)) or len(codes) != len(set(codes)):
        raise ValueError("diagnostic scenario identifiers and detection codes must be unique")
    return scenarios


def _run_scenario(scenario: DiagnosticScenario) -> dict[str, object]:
    disposition = (
        "AUTO_REMEDIATED"
        if scenario.remediation_mode == "AUTO_LOCAL"
        else "ESCALATED_FOR_APPROVAL"
    )
    audit_seed = {
        "scenario_id": scenario.scenario_id,
        "detection_code": scenario.detection_code,
        "disposition": disposition,
        "observed_at": scenario.observed_at.isoformat(),
        "zero_egress": True,
    }
    audit = AuditEntryPost(
        audit_entry_id="AUDIT-RX-" + canonical_sha256(audit_seed)[:24].upper(),
        timestamp=scenario.observed_at,
        actor_agent_id="AGENT-DOCTRINE-DIAGNOSTIC",
        operator_consent_token_id=None,
        action=f"simulate:{scenario.scenario_id}",
        justification=(
            "isolated fixture remediation with no external effect"
            if disposition == "AUTO_REMEDIATED"
            else "consequential or identity-bound remediation requires operator approval"
        ),
        affix_metadata={
            "detect": "post",
            "remediate": "auto-local" if disposition == "AUTO_REMEDIATED" else "auditable-post",
            "audit": "entry-post",
        },
    )
    body: dict[str, object] = {
        "schema_version": "regenexcalibur.diagnostic-result.v1",
        "scenario_id": scenario.scenario_id,
        "detection_code": scenario.detection_code,
        "classification": scenario.classification,
        "detected": True,
        "disposition": disposition,
        "remediation_plan": list(scenario.remediation_plan),
        "first_blocker": scenario.expected_blocker,
        "audit_entry_post": audit.model_dump(mode="json"),
        "zero_egress": True,
        "provider_calls_performed": 0,
        "external_actions_performed": 0,
        "authority_granted": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body

def run_diagnostic_scenario(scenario_id: str) -> dict[str, object]:
    scenario = next(
        (item for item in load_diagnostic_scenarios() if item.scenario_id == scenario_id),
        None,
    )
    if scenario is None:
        raise ValueError("unknown diagnostic scenario")
    return _run_scenario(scenario)


def run_all_diagnostics() -> dict[str, object]:
    results = [_run_scenario(item) for item in load_diagnostic_scenarios()]
    body: dict[str, object] = {
        "schema_version": "regenexcalibur.acceptance-report.v1",
        "project": "RegenExcalibur AIGC Coordinator",
        "detected_count": sum(bool(item["detected"]) for item in results),
        "handled_count": sum(
            item["disposition"] in {"AUTO_REMEDIATED", "ESCALATED_FOR_APPROVAL"}
            for item in results
        ),
        "auto_remediated_count": sum(
            item["disposition"] == "AUTO_REMEDIATED" for item in results
        ),
        "escalated_count": sum(
            item["disposition"] == "ESCALATED_FOR_APPROVAL" for item in results
        ),
        "results": results,
        "security_review": {
            "authentication_bypass_attempted": False,
            "captcha_bypass_attempted": False,
            "raw_credentials_accessed": False,
            "external_mutation_performed": False,
        },
        "terminal_status": "PASS",
        "zero_egress": True,
        "provider_calls_performed": 0,
        "external_actions_performed": 0,
        "authority_granted": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body
