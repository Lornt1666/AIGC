from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ALLOWED_COMPLIANCE_STATES = {
    "conformant",
    "not_applicable",
    "exception_requested",
    "nonconformant_blocking",
}


@dataclass(frozen=True)
class ConstitutionGateResult:
    passed: bool
    reason_codes: tuple[str, ...]
    details: tuple[str, ...]


class ConstitutionGate:
    """Deterministic AEC-001 validation without external actions.

    This gate validates the constitutional registry and a traceability manifest.
    It does not approve, merge, deploy, or infer human authority.
    """

    def __init__(self, registry: dict[str, Any]):
        self.registry = registry
        self.article_ids = {
            item.get("id")
            for item in registry.get("articles", [])
            if isinstance(item, dict)
        }

    @classmethod
    def from_path(cls, path: Path) -> "ConstitutionGate":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def validate_registry(self) -> ConstitutionGateResult:
        reasons: list[str] = []
        details: list[str] = []

        if self.registry.get("constitution_id") != "AEC-001":
            reasons.append("INVALID_CONSTITUTION_ID")
        if self.registry.get("authority_class") != "constitution":
            reasons.append("INVALID_AUTHORITY_CLASS")
        if self.registry.get("conflict_behavior") != "pause_for_accountable_human_ruling":
            reasons.append("UNSAFE_CONFLICT_BEHAVIOR")
        if self.registry.get("default_compliance_state") != "nonconformant_blocking":
            reasons.append("NON_FAIL_CLOSED_DEFAULT")
        if self.registry.get("external_action_performed") is not False:
            reasons.append("EXTERNAL_ACTION_FLAG_INVALID")
        if len(self.article_ids) != 32:
            reasons.append("ARTICLE_SET_INCOMPLETE_OR_DUPLICATED")
            details.append(f"expected 32 unique articles, found {len(self.article_ids)}")
        if set(self.registry.get("compliance_states", [])) != ALLOWED_COMPLIANCE_STATES:
            reasons.append("INVALID_COMPLIANCE_STATES")

        return ConstitutionGateResult(not reasons, tuple(reasons), tuple(details))

    def evaluate_manifest(self, manifest: dict[str, Any]) -> ConstitutionGateResult:
        reasons: list[str] = []
        details: list[str] = []

        affected = manifest.get("affected_articles")
        if not isinstance(affected, list) or not affected:
            reasons.append("MISSING_AFFECTED_ARTICLES")
            return ConstitutionGateResult(False, tuple(reasons), tuple(details))

        seen: set[str] = set()
        for entry in affected:
            if not isinstance(entry, dict):
                reasons.append("INVALID_ARTICLE_ENTRY")
                continue
            article_id = entry.get("article_id")
            state = entry.get("compliance_state")
            rationale = str(entry.get("rationale", "")).strip()

            if article_id not in self.article_ids:
                reasons.append("UNKNOWN_ARTICLE")
                details.append(str(article_id))
            if article_id in seen:
                reasons.append("DUPLICATE_ARTICLE")
                details.append(str(article_id))
            seen.add(str(article_id))
            if state not in ALLOWED_COMPLIANCE_STATES:
                reasons.append("INVALID_COMPLIANCE_STATE")
                details.append(f"{article_id}:{state}")
            if not rationale:
                reasons.append("MISSING_RATIONALE")
                details.append(str(article_id))
            if state == "nonconformant_blocking":
                reasons.append("NONCONFORMANT_BLOCKING")
                details.append(str(article_id))
            if state == "exception_requested" and not manifest.get("exceptions_or_waivers"):
                reasons.append("EXCEPTION_WITHOUT_WAIVER")
                details.append(str(article_id))

        for field in (
            "revision",
            "test_plan",
            "evidence_plan",
            "rollback_boundary",
            "data_classification",
            "jurisdiction_classification",
        ):
            value = manifest.get(field)
            if value in (None, "", [], {}):
                reasons.append("MISSING_REQUIRED_TRACEABILITY_FIELD")
                details.append(field)

        if manifest.get("external_action_performed") not in (None, False):
            reasons.append("EXTERNAL_ACTION_NOT_ALLOWED")

        return ConstitutionGateResult(not reasons, tuple(reasons), tuple(details))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def unique_reason_codes(results: Iterable[ConstitutionGateResult]) -> tuple[str, ...]:
    return tuple(sorted({code for result in results for code in result.reason_codes}))
