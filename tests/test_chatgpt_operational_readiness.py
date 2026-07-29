from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.core.chatgpt_operational_readiness import (
    DEFAULT_CONFIG,
    DEFAULT_SCHEMA,
    ChatGPTOperationalReadinessError,
    evaluate_chatgpt_operational_readiness,
)


def _config() -> dict:
    return json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "readiness.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_current_score_is_truthful_and_not_100() -> None:
    result = evaluate_chatgpt_operational_readiness()
    assert result.score == 49.5
    assert result.release_100_permitted is False
    assert result.hosted_ci_replacement_allowed is False
    assert result.external_action_performed is False
    assert result.safety_invariants_preserved is True


def test_hosted_ci_replacement_cannot_be_enabled(tmp_path: Path) -> None:
    payload = _config()
    payload["safety_invariants"]["hosted_ci_replacement_allowed"] = True
    with pytest.raises(ChatGPTOperationalReadinessError):
        evaluate_chatgpt_operational_readiness(_write(tmp_path, payload), DEFAULT_SCHEMA)


def test_100_points_without_all_evidence_truths_is_not_release_100(tmp_path: Path) -> None:
    payload = _config()
    for category in payload["categories"]:
        category["status"] = "PRODUCTION_ACCEPTED"
    result = evaluate_chatgpt_operational_readiness(_write(tmp_path, payload), DEFAULT_SCHEMA)
    assert result.score == 100
    assert result.release_100_permitted is False


def test_release_100_requires_all_evidence_truths_and_preserved_invariants(tmp_path: Path) -> None:
    payload = _config()
    for category in payload["categories"]:
        category["status"] = "PRODUCTION_ACCEPTED"
    for key in payload["evidence_truths"]:
        payload["evidence_truths"][key] = True
    result = evaluate_chatgpt_operational_readiness(_write(tmp_path, payload), DEFAULT_SCHEMA)
    assert result.score == 100
    assert result.release_100_permitted is True
    assert result.hosted_ci_replacement_allowed is False


def test_duplicate_category_ids_fail_closed(tmp_path: Path) -> None:
    payload = _config()
    payload["categories"][1]["category_id"] = payload["categories"][0]["category_id"]
    with pytest.raises(ChatGPTOperationalReadinessError, match="unique"):
        evaluate_chatgpt_operational_readiness(_write(tmp_path, payload), DEFAULT_SCHEMA)


def test_weights_must_total_100(tmp_path: Path) -> None:
    payload = _config()
    payload["categories"][0]["weight"] = 9
    with pytest.raises(ChatGPTOperationalReadinessError, match="total"):
        evaluate_chatgpt_operational_readiness(_write(tmp_path, payload), DEFAULT_SCHEMA)
