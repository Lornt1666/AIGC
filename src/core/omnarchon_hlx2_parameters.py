from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "omnarchon_hlx2_parameters.json"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "omnarchon_hlx2_parameters.schema.json"


class OmnarchonParametersError(ValueError):
    """Raised when the OMNARCHON-HLX2 parameter contract is invalid or unsafe."""


def _load_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OmnarchonParametersError(f"Unable to load JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise OmnarchonParametersError(f"Expected a JSON object: {path}")
    return payload


def canonical_digest(value: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def validate_parameters(
    parameters: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    Draft202012Validator.check_schema(dict(schema))
    validator = Draft202012Validator(
        dict(schema),
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(dict(parameters)),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        messages: list[str] = []
        for error in errors[:12]:
            location = "$" + "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}"
                for part in error.absolute_path
            )
            messages.append(f"{location}: {error.message}")
        raise OmnarchonParametersError(
            "OMNARCHON-HLX2 schema validation failed: " + "; ".join(messages)
        )

    document = json.loads(json.dumps(parameters))
    safety = document["safety_and_authority"]
    prohibited_true = {
        "automation_can_self_approve",
        "automatic_merge_allowed",
        "automatic_external_commitment_allowed",
        "direct_main_write_allowed",
        "terraform_apply_allowed",
        "provider_resource_mutation_allowed",
        "credential_access_allowed",
        "raw_secrets_allowed",
        "hosted_ci_replacement_allowed",
        "external_action_performed",
    }
    weakened = sorted(key for key in prohibited_true if safety[key] is not False)
    if weakened:
        raise OmnarchonParametersError(
            "OMNARCHON-HLX2 cannot weaken AIGC authority boundaries: "
            + ", ".join(weakened)
        )
    if safety["operator_review_required"] is not True:
        raise OmnarchonParametersError("Operator review must remain required.")

    required_sequence = [
        "receive",
        "interpret",
        "decompose",
        "expand",
        "contextualize",
        "verify",
        "scale",
        "archetypize",
        "counter_archetypize",
        "transcend",
        "model",
        "generate",
        "compare",
        "red_team",
        "reconcile",
        "optimize",
        "architect",
        "procure",
        "program",
        "validate",
        "communicate",
        "evolve",
    ]
    if document["hlx2_sequence"] != required_sequence:
        raise OmnarchonParametersError("HLX2 execution order is not canonical.")

    if document["epistemic_governance"]["literal_omniscience_claim_allowed"]:
        raise OmnarchonParametersError("Literal omniscience claims are prohibited.")
    if document["metatranscended_archetype_engine"]["decorative_archetypes_allowed"]:
        raise OmnarchonParametersError("Archetypes must change operational design.")
    if document["optimization"]["complexity_for_prestige_allowed"]:
        raise OmnarchonParametersError("Prestige complexity is prohibited.")

    protected_authorities = set(document["aigc_binding"]["must_not_replace"])
    required_protected = {
        "canonical_repository_truth",
        "exact_revision_binding",
        "hosted_ci_evidence",
        "phase5_external_authority",
        "operator_review",
        "connector_specific_approval",
        "immutable_execution_receipts",
    }
    if not required_protected <= protected_authorities:
        missing = sorted(required_protected - protected_authorities)
        raise OmnarchonParametersError(
            "Required AIGC authorities are not protected: " + ", ".join(missing)
        )
    return document


def load_parameters(
    config_path: Path = DEFAULT_CONFIG_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    return validate_parameters(_load_object(config_path), _load_object(schema_path))


def build_receipt(parameters: Mapping[str, Any]) -> dict[str, Any]:
    schema = _load_object(DEFAULT_SCHEMA_PATH)
    document = validate_parameters(parameters, schema)
    digest = canonical_digest(document)
    return {
        "receipt_id": f"AIGC-OMNARCHON-HLX2-{digest[:20].upper()}",
        "contract_id": document["contract_id"],
        "contract_version": document["contract_version"],
        "parameter_digest": digest,
        "architecture": document["architecture"]["name"],
        "execution_kernel": document["architecture"]["execution_kernel"],
        "default_enabled": document["activation"]["default_enabled"],
        "operator_review_required": True,
        "automatic_merge_allowed": False,
        "automatic_external_commitment_allowed": False,
        "external_action_performed": False,
    }


def main() -> int:
    parameters = load_parameters()
    print(json.dumps(build_receipt(parameters), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
