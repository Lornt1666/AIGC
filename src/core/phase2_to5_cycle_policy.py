from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.core.contract_validator import validate_artifact


POLICY_SCHEMA = "phase2_to5_cycle_policy"
POLICY_RELATIVE_PATH = Path("config/phase2_to5_cycle_policy.json")
AUTHORIZATION_ENV = "AIGC_PHASE2_TO5_OPERATOR_AUTHORIZATION"
REVIEW_ONLY_ENV = "AIGC_PHASE2_TO5_REVIEW_ONLY"
AUTHORIZED_NATIVE_CYCLE_CONTEXT = "authorized_native_phase2_to5_review_workflow"


class Phase2To5CyclePolicyError(ValueError):
    """Raised when Phase 2–5 generation is not authorized by the active cycle policy."""


def load_phase2_to5_cycle_policy(project_root: Path) -> dict[str, Any]:
    path = project_root / POLICY_RELATIVE_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase2To5CyclePolicyError(f"Invalid Phase 2–5 cycle policy at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Phase2To5CyclePolicyError(f"Expected an object in Phase 2–5 cycle policy at {path}.")
    validate_artifact(POLICY_SCHEMA, payload)
    validate_phase2_to5_cycle_policy(payload)
    return payload


def validate_phase2_to5_cycle_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("external_action_performed") is not False:
        raise Phase2To5CyclePolicyError("Phase 2–5 cycle policy must not report an external action.")

    active_hold = _mapping(policy, "active_hold")
    if not isinstance(active_hold.get("enabled"), bool):
        raise Phase2To5CyclePolicyError("active_hold.enabled must be a boolean.")
    if active_hold.get("automatic_regeneration_allowed") is not False:
        raise Phase2To5CyclePolicyError(
            "Automatic Phase 2–5 regeneration must remain disabled."
        )
    if active_hold.get("external_contact_allowed") is not False:
        raise Phase2To5CyclePolicyError("External contact must remain disabled in the cycle policy.")
    if active_hold.get("production_locked") is not True:
        raise Phase2To5CyclePolicyError("Production must remain locked in the cycle policy.")
    if int(active_hold.get("maximum_scoped_internal_improvement_proposals", 0)) != 1:
        raise Phase2To5CyclePolicyError(
            "The active hold must allow exactly one scoped internal improvement proposal."
        )

    native_cycle = _mapping(policy, "authorized_native_cycle")
    if native_cycle.get("event_name") != "workflow_dispatch":
        raise Phase2To5CyclePolicyError(
            "Authorized Phase 2–5 generation must use workflow_dispatch."
        )
    if native_cycle.get("review_only") is not True:
        raise Phase2To5CyclePolicyError(
            "Authorized Phase 2–5 generation must remain review-only."
        )
    if not str(native_cycle.get("operator_authorization_phrase", "")).strip():
        raise Phase2To5CyclePolicyError(
            "Authorized Phase 2–5 generation requires an exact operator authorization phrase."
        )
    if not str(native_cycle.get("workflow_file", "")).strip():
        raise Phase2To5CyclePolicyError(
            "Authorized Phase 2–5 generation requires a workflow path."
        )
    if native_cycle.get("run_receipts_immutable") is not True:
        raise Phase2To5CyclePolicyError(
            "Authorized Phase 2–5 generation requires immutable run receipts."
        )

    phase6 = _mapping(policy, "phase6")
    if phase6.get("execution_mode") != "manual_handoff":
        raise Phase2To5CyclePolicyError("Phase 6 must remain in manual_handoff mode.")
    if phase6.get("fresh_exact_unexpired_acceptance_required") is not True:
        raise Phase2To5CyclePolicyError(
            "Phase 6 must require fresh exact acceptance of an unexpired packet."
        )

    connector_and_production = _mapping(policy, "connector_and_production_boundary")
    if connector_and_production.get("connectors_enabled") is not False:
        raise Phase2To5CyclePolicyError("Connectors must remain disabled in the cycle policy.")
    if connector_and_production.get("production_deployment_authorized") is not False:
        raise Phase2To5CyclePolicyError(
            "Production deployment must remain unauthorized in the cycle policy."
        )

    strategy = policy.get("next_cycle_strategy")
    if not isinstance(strategy, list) or not strategy or not all(
        isinstance(item, str) and item.strip() for item in strategy
    ):
        raise Phase2To5CyclePolicyError(
            "The active cycle policy must contain a non-empty next-cycle strategy."
        )
    proposal = _mapping(policy, "scoped_internal_improvement_proposal")
    if proposal.get("status") != "proposed_internal_only":
        raise Phase2To5CyclePolicyError(
            "The scoped internal improvement proposal must remain internal-only."
        )
    if proposal.get("apply_authorized") is not False:
        raise Phase2To5CyclePolicyError(
            "The scoped internal improvement proposal must not be applied automatically."
        )
    if proposal.get("external_action_performed") is not False:
        raise Phase2To5CyclePolicyError(
            "The scoped internal improvement proposal must not report an external action."
        )


def require_phase2_to5_generation_authorized(
    project_root: Path,
    phase: str,
    environ: Mapping[str, str] | None = None,
) -> None:
    policy = load_phase2_to5_cycle_policy(project_root)
    if not policy:
        raise Phase2To5CyclePolicyError(
            "Phase 2–5 generation is blocked because the durable cycle policy is missing."
        )
    if not _mapping(policy, "active_hold").get("enabled", False):
        return
    environment = environ if environ is not None else os.environ
    if native_cycle_is_authorized(policy, environment):
        return
    raise Phase2To5CyclePolicyError(
        f"{phase} generation is blocked by the active read-only Phase 4/5 hold. "
        "Use only the separately authorized native Phase 2–5 review workflow; "
        "do not regenerate artifacts locally."
    )


def native_cycle_is_authorized(
    policy: Mapping[str, Any],
    environ: Mapping[str, str],
) -> bool:
    native_cycle = _mapping(policy, "authorized_native_cycle")
    workflow_file = str(native_cycle.get("workflow_file", "")).strip()
    workflow_ref = str(environ.get("GITHUB_WORKFLOW_REF", ""))
    expected_fragment = f"/{workflow_file}@"
    return (
        str(environ.get(AUTHORIZATION_ENV, ""))
        == str(native_cycle.get("operator_authorization_phrase", ""))
        and str(environ.get(REVIEW_ONLY_ENV, "")).lower() == "true"
        and str(environ.get("GITHUB_ACTIONS", "")).lower() == "true"
        and str(environ.get("GITHUB_EVENT_NAME", "")) == str(native_cycle.get("event_name", ""))
        and bool(str(environ.get("GITHUB_RUN_ID", "")).strip())
        and bool(workflow_file)
        and expected_fragment in workflow_ref
    )


def authorized_native_cycle_provenance(
    policy: Mapping[str, Any],
    environ: Mapping[str, str],
) -> dict[str, str]:
    if not native_cycle_is_authorized(policy, environ):
        return {}
    native_cycle = _mapping(policy, "authorized_native_cycle")
    return {
        "generation_context": AUTHORIZED_NATIVE_CYCLE_CONTEXT,
        "workflow_file": str(native_cycle.get("workflow_file", "")),
        "event_name": str(native_cycle.get("event_name", "")),
        "github_run_id": str(environ.get("GITHUB_RUN_ID", "")),
        "github_workflow_ref": str(environ.get("GITHUB_WORKFLOW_REF", "")),
    }


def packet_was_generated_by_authorized_native_cycle(
    policy: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> bool:
    provenance = packet.get("generation_provenance", {})
    if not isinstance(provenance, Mapping):
        return False
    native_cycle = _mapping(policy, "authorized_native_cycle")
    return (
        provenance.get("generation_context") == AUTHORIZED_NATIVE_CYCLE_CONTEXT
        and provenance.get("workflow_file") == native_cycle.get("workflow_file")
        and provenance.get("event_name") == native_cycle.get("event_name")
        and bool(str(provenance.get("github_run_id", "")).strip())
        and f"/{native_cycle.get('workflow_file', '')}@"
        in str(provenance.get("github_workflow_ref", ""))
    )


def active_hold_directive(policy: Mapping[str, Any]) -> dict[str, Any]:
    active_hold = _mapping(policy, "active_hold")
    phase6 = _mapping(policy, "phase6")
    native_cycle = _mapping(policy, "authorized_native_cycle")
    return {
        "status": "active" if active_hold.get("enabled") else "inactive",
        "phase4_input_review_mode": active_hold.get("phase4_input_review_mode", "read_only"),
        "phase5_input_review_mode": active_hold.get(
            "phase5_input_review_mode",
            "read_only_archived_expired_packets",
        ),
        "packet_regeneration_allowed": False,
        "maximum_scoped_internal_improvement_proposals": active_hold.get(
            "maximum_scoped_internal_improvement_proposals",
            1,
        ),
        "phase6_execution_mode": phase6.get("execution_mode", "manual_handoff"),
        "production_locked": active_hold.get("production_locked", True),
        "external_contact_allowed": active_hold.get("external_contact_allowed", False),
        "native_workflow_run_requires_explicit_operator_authorization": True,
        "authorized_native_workflow_file": native_cycle.get("workflow_file", ""),
        "fresh_exact_unexpired_acceptance_required_for_phase6": phase6.get(
            "fresh_exact_unexpired_acceptance_required",
            True,
        ),
        "external_action_performed": False,
    }


def next_cycle_policy_snapshot(policy: Mapping[str, Any]) -> dict[str, Any]:
    validate_phase2_to5_cycle_policy(policy)
    proposal = _mapping(policy, "scoped_internal_improvement_proposal")
    return {
        "policy_source": str(POLICY_RELATIVE_PATH),
        "policy_version": policy.get("contract_version", ""),
        "next_cycle_strategy": list(policy.get("next_cycle_strategy", [])),
        "manual_handoff_directive": active_hold_directive(policy),
        "scoped_internal_improvement_proposal": dict(proposal),
        "external_action_performed": False,
    }


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, Mapping):
        raise Phase2To5CyclePolicyError(f"{key} must be an object.")
    return value
