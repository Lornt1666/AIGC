from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from scripts.validate_aigc_llm_stack import validate
from src.llm_stack.models import LLMStackConfig, ModelConfig
from src.llm_stack.orchestrator import (
    LLMLifecycleOrchestrator,
    plan_llm_lifecycle,
)
from src.llm_stack.reference_data import ByteTokenizer, NextTokenDataset
from src.llm_stack.serving_api import create_llm_serving_app


ROOT = Path(__file__).resolve().parents[1]


def _config() -> dict[str, object]:
    return json.loads(
        (ROOT / "config" / "aigc_llm_stack.v1.json").read_text(encoding="utf-8")
    )


def test_committed_config_validates_against_schema_and_contract() -> None:
    config = _config()
    schema = json.loads(
        (ROOT / "schemas" / "aigc_llm_stack.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(config)
    validated = LLMStackConfig.model_validate(config)
    assert validated.resources.maximum_training_cost_cad == 0
    assert validated.production_activation_authorized is False


def test_byte_tokenizer_is_lossless_and_rejects_invalid_ids() -> None:
    tokenizer = ByteTokenizer()
    text = "RegenExcalibur ⚔️ — 安全"
    assert tokenizer.decode(tokenizer.encode(text)) == text
    with pytest.raises(ValueError, match="0 through 255"):
        tokenizer.decode([256])


def test_next_token_dataset_builds_exact_shifted_windows_and_is_bounded() -> None:
    tokenizer = ByteTokenizer()
    dataset = NextTokenDataset(["abcdef"], tokenizer, 3, stride=2)
    assert dataset[0] == ((97, 98, 99), (98, 99, 100))
    assert dataset[1] == ((99, 100, 101), (100, 101, 102))
    with pytest.raises(ValueError, match="maximum_samples"):
        NextTokenDataset(["abcdef"], tokenizer, 2, stride=1, maximum_samples=1)


def test_lifecycle_plan_is_deterministic_zero_action_and_fail_closed() -> None:
    first = plan_llm_lifecycle(_config())
    second = plan_llm_lifecycle(_config())
    assert first == second
    assert first["terminal_status"] == "BLOCKED"
    assert first["training_steps_performed"] == 0
    assert first["provider_calls_performed"] == 0
    assert first["external_actions_performed"] == 0
    assert first["authority_granted"] is False
    assert first["production_ready"] is False
    serving = next(stage for stage in first["stages"] if stage["stage"] == "SERVING")
    assert serving["status"] == "BLOCKED_PERMISSION"


def test_requested_training_remains_blocked_without_execution_boundary() -> None:
    config = _config()
    config["training"]["pretraining"]["enabled"] = True
    receipt = plan_llm_lifecycle(config)
    pretrain = next(stage for stage in receipt["stages"] if stage["stage"] == "PRETRAIN")
    assert pretrain["status"] == "BLOCKED_PERMISSION"
    assert receipt["training_steps_performed"] == 0


def test_orchestrator_builds_local_data_and_refuses_training() -> None:
    config = _config()
    config["model"]["max_sequence_length"] = 8
    orchestrator = LLMLifecycleOrchestrator(config)
    dataset = orchestrator.build_dataset(["0123456789"])
    assert len(dataset) == 1
    assert orchestrator.plan()["terminal_status"] == "BLOCKED"
    with pytest.raises(PermissionError, match="scoped permit"):
        orchestrator.run_training()


def test_invalid_transformer_dimensions_are_rejected() -> None:
    with pytest.raises(ValidationError, match="divisible"):
        ModelConfig(
            architecture="GPT_CAUSAL_REFERENCE_V1", d_model=130, n_heads=8
        )


def test_serving_boundary_is_disabled_by_default_and_request_bounded() -> None:
    client = TestClient(create_llm_serving_app())
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["runtime_loaded"] is False
    response = client.post("/generate", json={"prompt": "hello"})
    assert response.status_code == 503
    assert response.json()["detail"] == "no admitted model runtime is loaded"
    invalid = client.post(
        "/generate", json={"prompt": "hello", "maximum_new_tokens": 4097}
    )
    assert invalid.status_code == 422


def test_validator_emits_receipt_and_optional_torch_is_isolated() -> None:
    receipt = validate()
    assert len(receipt["receipt_sha256"]) == 64
    assert "src.llm_stack.torch_reference" not in __import__("sys").modules
    requirements = (ROOT / "requirements-llm-training.txt").read_text(
        encoding="utf-8"
    )
    assert "torch" in requirements
