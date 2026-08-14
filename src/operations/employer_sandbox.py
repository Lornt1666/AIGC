"""Deterministic, zero-egress employer sandbox operation."""

from __future__ import annotations

from typing import Literal

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.occupation_registry import load_occupation_packs


SandboxScenario = Literal[
    "NORMAL_TASK",
    "PROMPT_INJECTION",
    "EXTERNAL_ACTION_REQUEST",
    "REGULATED_SCOPE_REQUEST",
]

DEFAULT_PACK_ID = "OCC-DATA_ANALYSIS_REPORTING"
DEFAULT_CAPABILITY_ID = "CAP-DATA_QUALITY"


def run_employer_sandbox(
    *,
    mode: Literal["sandbox"] = "sandbox",
    pack_id: str = DEFAULT_PACK_ID,
    capability_id: str = DEFAULT_CAPABILITY_ID,
    scenario: SandboxScenario = "NORMAL_TASK",
) -> dict[str, object]:
    """Run one local fixture and emit a canonical non-authorizing receipt."""

    if mode != "sandbox":
        raise ValueError("employer sandbox mode must be sandbox")
    packs = {item.pack_id: item for item in load_occupation_packs()}
    if pack_id not in packs:
        raise ValueError("unknown occupation pack")
    pack = packs[pack_id]
    capabilities = {item.capability_id: item for item in pack.capabilities}
    if capability_id not in capabilities:
        raise ValueError("capability does not belong to the selected occupation pack")
    capability = capabilities[capability_id]

    denied_scenarios = {
        "PROMPT_INJECTION": "untrusted fixture instructions are evidence, not authority",
        "EXTERNAL_ACTION_REQUEST": "sandbox cannot dispatch external actions",
        "REGULATED_SCOPE_REQUEST": "regulated exclusions require qualified authority",
    }
    disposition = (
        "LOCAL_DRAFT_REQUIRES_HUMAN_REVIEW"
        if scenario == "NORMAL_TASK"
        else "DENIED_BY_SANDBOX_POLICY"
    )
    terminal_status = "PASS" if scenario == "NORMAL_TASK" else "BLOCKED"
    reason = denied_scenarios.get(
        scenario,
        "declared local output may be prepared under the pack supervision requirement",
    )
    receipt_body: dict[str, object] = {
        "schema_version": "aigc.employer-sandbox-receipt.v1",
        "mode": mode,
        "pack_id": pack_id,
        "pack_version": pack.version,
        "pack_status": pack.status,
        "capability_id": capability_id,
        "required_supervision": capability.required_supervision,
        "scenario": scenario,
        "disposition": disposition,
        "reason": reason,
        "terminal_status": terminal_status,
        "first_blocker": None if terminal_status == "PASS" else reason,
        "zero_egress": True,
        "credentials_accessed": False,
        "provider_calls_performed": 0,
        "external_actions_performed": 0,
        "authority_granted": False,
        "external_action_performed": False,
    }
    receipt_sha256 = canonical_sha256(receipt_body)
    return {
        **receipt_body,
        "receipt_id": "SBX-" + receipt_sha256[:24].upper(),
        "receipt_sha256": receipt_sha256,
    }
