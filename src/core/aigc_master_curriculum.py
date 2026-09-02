from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.core.contract_validator import validate_artifact


CURRICULUM_SCHEMA = "aigc_master_curriculum"
CURRICULUM_RELATIVE_PATH = Path("config/aigc_master_curriculum.json")
REQUIRED_CLASS_IDS = set(range(1, 16))


class AIGCMasterCurriculumError(ValueError):
    """Raised when the internal curriculum violates its governance boundary."""


def load_aigc_master_curriculum(project_root: Path) -> dict[str, Any]:
    path = project_root / CURRICULUM_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AIGCMasterCurriculumError(f"Master curriculum is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AIGCMasterCurriculumError(f"Master curriculum is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise AIGCMasterCurriculumError("Master curriculum must be a JSON object.")
    validate_artifact(CURRICULUM_SCHEMA, payload)
    validate_aigc_master_curriculum(payload)
    return payload


def validate_aigc_master_curriculum(curriculum: Mapping[str, Any]) -> None:
    if curriculum.get("operating_mode") != "internal_reference_only":
        raise AIGCMasterCurriculumError(
            "The master curriculum must remain an internal reference."
        )
    if curriculum.get("external_action_performed") is not False:
        raise AIGCMasterCurriculumError(
            "The master curriculum must not report an external action."
        )

    boundary = _mapping(curriculum, "governance_boundary")
    required_false = [
        "external_actions_authorized",
        "production_activation_authorized",
        "connector_activation_authorized",
        "hardware_or_cyber_physical_control_authorized",
        "raw_secret_storage_allowed",
    ]
    for key in required_false:
        if boundary.get(key) is not False:
            raise AIGCMasterCurriculumError(f"governance_boundary.{key} must remain false.")
    if boundary.get("behavior_changing_patch_requires_justice_approval") is not True:
        raise AIGCMasterCurriculumError(
            "Behavior-changing curriculum applications must require Justice approval."
        )
    if boundary.get("phase5_approval_required") is not True:
        raise AIGCMasterCurriculumError(
            "Curriculum applications must remain subject to Phase 5 approval."
        )
    if boundary.get("phase6_manual_handoff_only") is not True:
        raise AIGCMasterCurriculumError(
            "Curriculum applications must remain subject to manual Phase 6 handoff."
        )

    classes = curriculum.get("classes")
    if not isinstance(classes, list):
        raise AIGCMasterCurriculumError("Master curriculum classes must be a list.")
    class_ids = {item.get("class_id") for item in classes if isinstance(item, Mapping)}
    if class_ids != REQUIRED_CLASS_IDS or len(classes) != len(REQUIRED_CLASS_IDS):
        raise AIGCMasterCurriculumError(
            "Master curriculum must contain exactly one class for each ID from 1 through 15."
        )
    for item in classes:
        if not isinstance(item, Mapping):
            raise AIGCMasterCurriculumError("Each master curriculum class must be an object.")
        for key in (
            "title",
            "academic_focus",
            "occupational_application",
            "disciplinary_coordination",
        ):
            if not str(item.get(key, "")).strip():
                raise AIGCMasterCurriculumError(
                    f"Master curriculum class {item.get('class_id')} is missing {key}."
                )


def summarize_aigc_master_curriculum(curriculum: Mapping[str, Any]) -> dict[str, Any]:
    validate_aigc_master_curriculum(curriculum)
    return {
        "curriculum_id": curriculum.get("curriculum_id", ""),
        "status": curriculum.get("status", ""),
        "operating_mode": curriculum.get("operating_mode", ""),
        "class_count": len(curriculum.get("classes", [])),
        "class_titles": [
            f"{item['class_id']}. {item['title']}"
            for item in curriculum.get("classes", [])
            if isinstance(item, Mapping)
        ],
        "external_action_performed": False,
    }


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, Mapping):
        raise AIGCMasterCurriculumError(f"{key} must be an object.")
    return value
