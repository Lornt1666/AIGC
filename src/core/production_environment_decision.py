from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DECISION_PATH = ROOT / "config" / "production_environment_decision.json"
DEFAULT_SCHEMA_PATH = ROOT / "schemas" / "production_environment_decision.schema.json"

_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "private_key",
    "secret_value",
    "access_token",
    "refresh_token",
    "id_token",
    "api_key",
    "oauth_secret",
    "recovery_code",
    "phone_number",
)
_SAFE_NEGATIVE_CONTROL_KEYS = {
    "repository_secret_values_allowed",
    "phone_number_committed",
}
_PHONE_LIKE = re.compile(r"(?<![A-Za-z0-9])\+?\d[\d .()-]{8,}\d(?![A-Za-z0-9])")


class ProductionEnvironmentDecisionError(ValueError):
    """Raised when the environment decision violates its contract or privacy boundary."""


@dataclass(frozen=True)
class ProductionEnvironmentDecisionEvaluation:
    decision_digest: str
    accepted_baseline: bool
    contract_implementation_ready: bool
    isolated_staging_preparation_ready: bool
    resource_creation_ready: bool
    production_deployment_ready: bool
    unresolved_identifiers: tuple[str, ...]
    enabled_connectors: tuple[str, ...]
    default_deny_connectors: bool
    monthly_cloud_ceiling_cad: int
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-PRODUCTION-ENVIRONMENT-DECISION-EVALUATION-001",
            "contract_version": "1.0.0",
            "decision_digest": self.decision_digest,
            "accepted_baseline": self.accepted_baseline,
            "contract_implementation_ready": self.contract_implementation_ready,
            "isolated_staging_preparation_ready": self.isolated_staging_preparation_ready,
            "resource_creation_ready": self.resource_creation_ready,
            "production_deployment_ready": self.production_deployment_ready,
            "unresolved_identifiers": list(self.unresolved_identifiers),
            "enabled_connectors": list(self.enabled_connectors),
            "default_deny_connectors": self.default_deny_connectors,
            "monthly_cloud_ceiling_cad": self.monthly_cloud_ceiling_cad,
            "reason_codes": list(self.reason_codes),
            "external_action_performed": False,
        }


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def decision_digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _walk(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = [(path, value)]
    if isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(_walk(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]"))
    return found


def _validate_privacy_boundary(value: Mapping[str, Any]) -> None:
    for path, item in _walk(value):
        key = path.rsplit(".", 1)[-1].lower()
        if (
            key not in _SAFE_NEGATIVE_CONTROL_KEYS
            and any(fragment in key for fragment in _SENSITIVE_KEY_FRAGMENTS)
        ):
            raise ProductionEnvironmentDecisionError(
                f"Sensitive field is prohibited in the environment decision: {path}"
            )
        if isinstance(item, str) and _PHONE_LIKE.search(item):
            raise ProductionEnvironmentDecisionError(
                f"Direct phone/contact data is prohibited in source-controlled decisions: {path}"
            )


def load_and_validate_decision(
    decision_path: str | Path = DEFAULT_DECISION_PATH,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    decision_file = Path(decision_path)
    schema_file = Path(schema_path)
    try:
        decision = json.loads(decision_file.read_text(encoding="utf-8"))
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionEnvironmentDecisionError(
            "Unable to load the production environment decision contract"
        ) from exc
    if not isinstance(decision, dict) or not isinstance(schema, dict):
        raise ProductionEnvironmentDecisionError(
            "Environment decision and schema must both be JSON objects"
        )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(decision),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        messages: list[str] = []
        for error in errors[:10]:
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        raise ProductionEnvironmentDecisionError(
            "Production environment decision validation failed: "
            + "; ".join(messages)
        )
    _validate_privacy_boundary(decision)
    return decision


def evaluate_decision(
    decision: Mapping[str, Any],
) -> ProductionEnvironmentDecisionEvaluation:
    value = dict(decision)
    unresolved = tuple(sorted(str(item) for item in value["unresolved_identifiers"]))
    authority = dict(value["authority"])
    connectors = dict(value["connectors"])
    reasons: list[str] = []

    if unresolved:
        reasons.append("DEFERRED_IDENTIFIERS_REMAIN")
    if connectors.get("enabled"):
        reasons.append("PRODUCTION_CONNECTORS_ENABLED")
    if authority.get("resource_creation_authorized") is not False:
        reasons.append("RESOURCE_CREATION_AUTHORITY_INVALID")
    if authority.get("production_deployment_authorized") is not False:
        reasons.append("PRODUCTION_DEPLOYMENT_AUTHORITY_INVALID")

    accepted = value.get("decision_status") == "ACCEPTED_WITH_DEFERRED_IDENTIFIERS"
    contract_ready = (
        accepted
        and authority.get("contract_implementation_authorized") is True
        and not connectors.get("enabled")
    )
    staging_preparation_ready = (
        contract_ready
        and authority.get("isolated_staging_preparation_authorized") is True
    )

    # This contract records architecture decisions only. Resource creation and
    # production deployment require later candidate-bound approval receipts.
    return ProductionEnvironmentDecisionEvaluation(
        decision_digest=decision_digest(value),
        accepted_baseline=accepted,
        contract_implementation_ready=contract_ready,
        isolated_staging_preparation_ready=staging_preparation_ready,
        resource_creation_ready=False,
        production_deployment_ready=False,
        unresolved_identifiers=unresolved,
        enabled_connectors=tuple(str(item) for item in connectors.get("enabled") or ()),
        default_deny_connectors=bool(connectors.get("default_deny")),
        monthly_cloud_ceiling_cad=int(value["budget"]["monthly_ceiling"]),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def evaluate_decision_file(
    decision_path: str | Path = DEFAULT_DECISION_PATH,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> ProductionEnvironmentDecisionEvaluation:
    return evaluate_decision(load_and_validate_decision(decision_path, schema_path))


def main() -> int:
    evaluation = evaluate_decision_file()
    print(json.dumps(evaluation.to_dict(), indent=2, sort_keys=True))
    return 0 if evaluation.contract_implementation_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
