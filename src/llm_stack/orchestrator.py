from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.epistemic.canonicalization import canonical_sha256
from src.llm_stack.models import LLMStackConfig, LifecycleReceipt, LifecycleStage
from src.llm_stack.reference_data import ByteTokenizer, NextTokenDataset


class LLMLifecycleOrchestrator:
    """Bounded lifecycle facade with no implicit training or deployment effects."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = LLMStackConfig.model_validate(config)
        self.tokenizer = ByteTokenizer()

    @classmethod
    def from_path(cls, path: str | Path) -> "LLMLifecycleOrchestrator":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(payload)

    def build_dataset(self, texts: list[str]) -> NextTokenDataset:
        training = self.config.training.pretraining
        return NextTokenDataset(
            texts,
            self.tokenizer,
            self.config.model.max_sequence_length,
            maximum_samples=training.maximum_steps * training.batch_size,
        )

    def plan(self) -> dict[str, object]:
        return plan_llm_lifecycle(self.config.model_dump(mode="json"))

    def run_training(self) -> None:
        raise PermissionError(
            "training requires verified data, compute, budget, and a scoped permit"
        )


def plan_llm_lifecycle(config: dict[str, Any]) -> dict[str, object]:
    """Validate and coordinate the lifecycle without training, providers, or deployment."""

    validated = LLMStackConfig.model_validate(config)
    training = validated.training
    data_status = "READY_LOCAL" if validated.data.rights_verified else "BLOCKED_PERMISSION"
    stages = (
        LifecycleStage(
            stage="DATA_ADMISSION",
            status=data_status,
            reason=(
                "synthetic or rights-verified repository data admitted"
                if data_status == "READY_LOCAL"
                else "training rights are not verified"
            ),
        ),
        LifecycleStage(
            stage="TOKENIZER",
            status="READY_LOCAL",
            reason="byte reference tokenizer is deterministic and lossless",
        ),
        LifecycleStage(
            stage="MODEL",
            status="READY_LOCAL",
            reason="causal-transformer dimensions and bounds validate",
        ),
        _training_stage("PRETRAIN", training.pretraining.enabled),
        _training_stage("SFT", training.supervised_finetuning.enabled),
        _training_stage("PREFERENCE_ALIGNMENT", training.preference_alignment.enabled),
        LifecycleStage(
            stage="EVALUATION",
            status="BLOCKED_PERMISSION",
            reason="model checkpoint and benchmark provenance do not yet exist",
        ),
        LifecycleStage(
            stage="SERVING",
            status="BLOCKED_PERMISSION",
            reason="serving is PLAN_ONLY and has no deployed model identity or production permit",
        ),
    )
    config_payload = validated.model_dump(mode="json")
    config_sha256 = canonical_sha256(config_payload)
    receipt_seed = {
        "config_sha256": config_sha256,
        "stages": [stage.model_dump(mode="json") for stage in stages],
        "provider_calls_performed": 0,
        "training_steps_performed": 0,
        "external_actions_performed": 0,
    }
    receipt_sha256 = canonical_sha256(receipt_seed)
    receipt = LifecycleReceipt(
        receipt_id="LLMPLAN-" + receipt_sha256[:24].upper(),
        config_sha256=config_sha256,
        receipt_sha256=receipt_sha256,
        stages=stages,
        first_blocker=next(
            stage.reason for stage in stages if stage.status == "BLOCKED_PERMISSION"
        ),
        terminal_status="BLOCKED",
    )
    return receipt.model_dump(mode="json")


def _training_stage(stage: str, enabled: bool) -> LifecycleStage:
    if not enabled:
        return LifecycleStage(
            stage=stage,
            status="NOT_REQUESTED",
            reason="stage is disabled in the committed zero-spend configuration",
        )
    return LifecycleStage(
        stage=stage,
        status="BLOCKED_PERMISSION",
        reason="training requires verified compute, data lineage, budget, and an execution permit",
    )
