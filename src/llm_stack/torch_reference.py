"""Optional PyTorch reference implementation.

This module is intentionally excluded from the core runtime dependency set. Install
`requirements-llm-training.txt` in an isolated training environment before importing it.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import torch
from torch import nn
from torch.nn import functional as F

from src.llm_stack.models import ModelConfig


class CausalSelfAttention(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.n_heads = config.n_heads
        self.head_dimension = config.d_model // config.n_heads
        self.qkv = nn.Linear(config.d_model, config.d_model * 3)
        self.output = nn.Linear(config.d_model, config.d_model)
        self.dropout = config.dropout

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        batch, time, channels = values.shape
        qkv = self.qkv(values).view(
            batch, time, 3, self.n_heads, self.head_dimension
        )
        query, key, value = qkv.unbind(dim=2)
        query = query.transpose(1, 2)
        key = key.transpose(1, 2)
        value = value.transpose(1, 2)
        attended = F.scaled_dot_product_attention(
            query,
            key,
            value,
            dropout_p=self.dropout if self.training else 0.0,
            is_causal=True,
        )
        merged = attended.transpose(1, 2).contiguous().view(batch, time, channels)
        return self.output(merged)


class TransformerBlock(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.attention_norm = nn.LayerNorm(config.d_model)
        self.feed_forward_norm = nn.LayerNorm(config.d_model)
        self.attention = CausalSelfAttention(config)
        self.feed_forward = nn.Sequential(
            nn.Linear(config.d_model, config.d_ff),
            nn.GELU(),
            nn.Linear(config.d_ff, config.d_model),
            nn.Dropout(config.dropout),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        values = values + self.attention(self.attention_norm(values))
        return values + self.feed_forward(self.feed_forward_norm(values))


class GPTCausalLM(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.position_embedding = nn.Embedding(
            config.max_sequence_length, config.d_model
        )
        self.blocks = nn.ModuleList(
            TransformerBlock(config) for _ in range(config.n_layers)
        )
        self.final_norm = nn.LayerNorm(config.d_model)
        self.language_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        self.language_head.weight = self.token_embedding.weight

    def forward(
        self, token_ids: torch.Tensor, labels: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        if token_ids.ndim != 2:
            raise ValueError("token_ids must have shape [batch, sequence]")
        _, sequence = token_ids.shape
        if sequence > self.config.max_sequence_length:
            raise ValueError("sequence exceeds configured maximum")
        positions = torch.arange(sequence, device=token_ids.device)
        hidden = self.token_embedding(token_ids) + self.position_embedding(positions)
        for block in self.blocks:
            hidden = block(hidden)
        logits = self.language_head(self.final_norm(hidden))
        loss = None
        if labels is not None:
            if labels.shape != token_ids.shape:
                raise ValueError("labels must match token_ids shape")
            loss = F.cross_entropy(
                logits.reshape(-1, logits.size(-1)), labels.reshape(-1)
            )
        return logits, loss


@torch.no_grad()
def generate(
    model: GPTCausalLM,
    token_ids: torch.Tensor,
    *,
    maximum_new_tokens: int,
    temperature: float = 1.0,
    top_k: int | None = 50,
    generator: torch.Generator | None = None,
) -> torch.Tensor:
    if maximum_new_tokens < 1 or maximum_new_tokens > 4096:
        raise ValueError("maximum_new_tokens must be between 1 and 4096")
    if not math.isfinite(temperature) or temperature <= 0 or temperature > 5:
        raise ValueError("temperature must be finite and between 0 and 5")
    model.eval()
    generated = token_ids
    for _ in range(maximum_new_tokens):
        context = generated[:, -model.config.max_sequence_length :]
        logits, _ = model(context)
        next_logits = logits[:, -1, :] / temperature
        if top_k is not None:
            if top_k < 1:
                raise ValueError("top_k must be positive")
            threshold = torch.topk(next_logits, min(top_k, next_logits.size(-1))).values[:, -1:]
            next_logits = next_logits.masked_fill(next_logits < threshold, float("-inf"))
        probabilities = torch.softmax(next_logits, dim=-1)
        next_token = torch.multinomial(probabilities, 1, generator=generator)
        generated = torch.cat((generated, next_token), dim=1)
    return generated


def train_epoch(
    model: GPTCausalLM,
    batches: Iterable[tuple[torch.Tensor, torch.Tensor]],
    optimizer: torch.optim.Optimizer,
    *,
    device: torch.device,
    maximum_steps: int,
    gradient_clip_norm: float = 1.0,
) -> dict[str, float | int]:
    if maximum_steps < 1:
        raise ValueError("maximum_steps must be positive")
    model.train()
    total_loss = 0.0
    steps = 0
    for inputs, targets in batches:
        if steps >= maximum_steps:
            break
        optimizer.zero_grad(set_to_none=True)
        _, loss = model(inputs.to(device), targets.to(device))
        if loss is None or not torch.isfinite(loss):
            raise RuntimeError("training produced a non-finite loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm)
        optimizer.step()
        steps += 1
        total_loss += float(loss.detach().cpu())
    if steps == 0:
        raise ValueError("training iterator produced no batches")
    return {"steps": steps, "mean_loss": total_loss / steps}


def pretrain_epoch(*args, **kwargs) -> dict[str, float | int]:
    """Run one bounded next-token epoch with the shared causal-LM objective."""

    return train_epoch(*args, **kwargs)


def supervised_finetune_epoch(*args, **kwargs) -> dict[str, float | int]:
    """Run one bounded SFT epoch over formatted instruction examples."""

    return train_epoch(*args, **kwargs)


def dpo_loss(
    policy_chosen_log_prob: torch.Tensor,
    policy_rejected_log_prob: torch.Tensor,
    reference_chosen_log_prob: torch.Tensor,
    reference_rejected_log_prob: torch.Tensor,
    *,
    beta: float = 0.1,
) -> torch.Tensor:
    """Bounded preference objective; dataset provenance remains an external gate."""

    if not math.isfinite(beta) or beta <= 0:
        raise ValueError("beta must be positive and finite")
    policy_ratio = policy_chosen_log_prob - policy_rejected_log_prob
    reference_ratio = reference_chosen_log_prob - reference_rejected_log_prob
    return -F.logsigmoid(beta * (policy_ratio - reference_ratio)).mean()
