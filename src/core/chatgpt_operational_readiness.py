from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "chatgpt_operational_readiness.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "chatgpt_operational_readiness.schema.json"
DEFAULT_OUTPUT = ROOT / "reports" / "artifacts" / "chatgpt_operational_readiness" / "current.json"


class ChatGPTOperationalReadinessError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatGPTOperationalReadinessResult:
    contract_id: str
    target: str
    score: float
    score_max: int
    category_scores: list[dict[str, Any]]
    first_incomplete_category: str | None
    evidence_truths: dict[str, bool]
    safety_invariants_preserved: bool
    release_100_permitted: bool
    hosted_ci_replacement_allowed: bool
    external_action_performed: bool


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ChatGPTOperationalReadinessError(f"Expected an object at {path}")
    return payload


def evaluate_chatgpt_operational_readiness(
    config_path: Path = DEFAULT_CONFIG,
    schema_path: Path = DEFAULT_SCHEMA,
) -> ChatGPTOperationalReadinessResult:
    config = _load(config_path)
    schema = _load(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(config), key=lambda item: tuple(item.path))
    if errors:
        raise ChatGPTOperationalReadinessError(
            "Schema validation failed: " + "; ".join(error.message for error in errors)
        )

    categories = list(config["categories"])
    if sum(int(item["weight"]) for item in categories) != int(config["score_max"]):
        raise ChatGPTOperationalReadinessError("Category weights must total score_max")
    ids = [str(item["category_id"]) for item in categories]
    if len(ids) != len(set(ids)):
        raise ChatGPTOperationalReadinessError("Category IDs must be unique")

    policy = config["score_policy"]
    score = 0.0
    category_scores: list[dict[str, Any]] = []
    first_incomplete: str | None = None
    for item in categories:
        multiplier = float(policy[item["status"]])
        earned = round(float(item["weight"]) * multiplier, 2)
        score += earned
        if item["status"] != "PRODUCTION_ACCEPTED" and first_incomplete is None:
            first_incomplete = str(item["category_id"])
        category_scores.append({
            "category_id": item["category_id"],
            "status": item["status"],
            "weight": item["weight"],
            "earned": earned,
        })

    evidence_truths = {str(key): bool(value) for key, value in config["evidence_truths"].items()}
    invariants = dict(config["safety_invariants"])
    invariants_preserved = all(value is False for value in invariants.values())
    release_100 = (
        round(score, 2) == float(config["score_max"])
        and all(evidence_truths.values())
        and invariants_preserved
        and config["current_authority"]["operator_review_required"] is True
    )
    return ChatGPTOperationalReadinessResult(
        contract_id=config["contract_id"],
        target=config["target"],
        score=round(score, 2),
        score_max=int(config["score_max"]),
        category_scores=category_scores,
        first_incomplete_category=first_incomplete,
        evidence_truths=evidence_truths,
        safety_invariants_preserved=invariants_preserved,
        release_100_permitted=release_100,
        hosted_ci_replacement_allowed=bool(invariants["hosted_ci_replacement_allowed"]),
        external_action_performed=False,
    )


def write_chatgpt_operational_readiness_receipt(
    output_path: Path = DEFAULT_OUTPUT,
) -> Path:
    result = evaluate_chatgpt_operational_readiness()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = write_chatgpt_operational_readiness_receipt()
    print(path)
