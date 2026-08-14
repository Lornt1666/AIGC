from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract


class DataConfig(NexusContract):
    source_kind: Literal["SYNTHETIC_FIXTURE", "RIGHTS_VERIFIED_CORPUS"]
    paths: tuple[str, ...] = Field(min_length=1, max_length=128)
    rights_verified: bool
    contains_personal_data: Literal[False] = False

    @model_validator(mode="after")
    def enforce_rights(self) -> "DataConfig":
        if self.source_kind == "RIGHTS_VERIFIED_CORPUS" and not self.rights_verified:
            raise ValueError("a non-synthetic corpus requires verified training rights")
        if any(not item.strip() or item.startswith(("/", "~")) for item in self.paths):
            raise ValueError("data paths must be non-empty repository-relative paths")
        return self


class TokenizerConfig(NexusContract):
    implementation: Literal["BYTE_REFERENCE_V1"]
    vocab_size: Literal[256] = 256


class ModelConfig(NexusContract):
    architecture: Literal["GPT_CAUSAL_REFERENCE_V1"]
    vocab_size: int = Field(default=256, ge=32, le=262144)
    d_model: int = Field(default=128, ge=32, le=16384)
    n_layers: int = Field(default=4, ge=1, le=256)
    n_heads: int = Field(default=4, ge=1, le=256)
    d_ff: int = Field(default=512, ge=64, le=65536)
    max_sequence_length: int = Field(default=256, ge=8, le=131072)
    dropout: float = Field(default=0.1, ge=0, lt=1)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "ModelConfig":
        if self.d_model % self.n_heads:
            raise ValueError("d_model must be divisible by n_heads")
        if self.d_ff < self.d_model:
            raise ValueError("d_ff must be at least d_model")
        return self


class TrainingStageConfig(NexusContract):
    enabled: bool = False
    epochs: int = Field(default=1, ge=1, le=10000)
    batch_size: int = Field(default=1, ge=1, le=65536)
    learning_rate: float = Field(default=0.0003, gt=0, le=1)
    maximum_steps: int = Field(default=100, ge=1, le=1000000000)


class TrainingConfig(NexusContract):
    device: Literal["cpu", "cuda", "mps"] = "cpu"
    pretraining: TrainingStageConfig
    supervised_finetuning: TrainingStageConfig
    preference_alignment: TrainingStageConfig
    alignment_method: Literal["DPO", "PPO_RLHF"] = "DPO"
    checkpoint_directory: str = Field(pattern=r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")
    execution_authorized: Literal[False] = False


class EvaluationConfig(NexusContract):
    required: Literal[True] = True
    maximum_benchmark_examples: int = Field(default=100, ge=1, le=100000)
    require_safety_suite: Literal[True] = True
    require_data_contamination_check: Literal[True] = True


class ServingConfig(NexusContract):
    mode: Literal["PLAN_ONLY"] = "PLAN_ONLY"
    maximum_new_tokens: int = Field(default=128, ge=1, le=4096)
    minimum_temperature: float = Field(default=0.01, gt=0, le=2)
    maximum_temperature: float = Field(default=1.5, gt=0, le=5)
    authentication_required: Literal[True] = True
    rate_limit_required: Literal[True] = True

    @model_validator(mode="after")
    def validate_temperature_range(self) -> "ServingConfig":
        if self.minimum_temperature > self.maximum_temperature:
            raise ValueError("minimum_temperature cannot exceed maximum_temperature")
        return self


class ResourceEnvelope(NexusContract):
    maximum_training_cost_cad: float = Field(default=0, ge=0, le=100000000)
    maximum_gpu_hours: float = Field(default=0, ge=0, le=100000000)
    maximum_dataset_bytes: int = Field(default=1048576, ge=1, le=1000000000000000)
    exact_compute_identity: str | None = None
    expires_at: str | None = None


class LLMStackConfig(NexusContract):
    schema_version: Literal["aigc.llm-stack.v1"]
    stack_id: str = Field(pattern=r"^LLM-STACK-[A-Z0-9_-]{4,80}$")
    status: Literal["DRAFT"]
    data: DataConfig
    tokenizer: TokenizerConfig
    model: ModelConfig
    training: TrainingConfig
    evaluation: EvaluationConfig
    serving: ServingConfig
    resources: ResourceEnvelope
    provider_calls_enabled: Literal[False] = False
    external_action_authorized: Literal[False] = False
    production_activation_authorized: Literal[False] = False


class LifecycleStage(NexusContract):
    stage: Literal[
        "DATA_ADMISSION",
        "TOKENIZER",
        "MODEL",
        "PRETRAIN",
        "SFT",
        "PREFERENCE_ALIGNMENT",
        "EVALUATION",
        "SERVING",
    ]
    status: Literal["READY_LOCAL", "NOT_REQUESTED", "BLOCKED_PERMISSION"]
    reason: str = Field(min_length=1, max_length=1000)


class LifecycleReceipt(NexusContract):
    schema_version: Literal["aigc.llm-lifecycle-receipt.v1"] = (
        "aigc.llm-lifecycle-receipt.v1"
    )
    receipt_id: str = Field(pattern=r"^LLMPLAN-[A-F0-9]{24}$")
    config_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    stages: tuple[LifecycleStage, ...]
    first_blocker: str
    terminal_status: Literal["BLOCKED"]
    provider_calls_performed: Literal[0] = 0
    training_steps_performed: Literal[0] = 0
    external_actions_performed: Literal[0] = 0
    authority_granted: Literal[False] = False
    production_ready: Literal[False] = False
