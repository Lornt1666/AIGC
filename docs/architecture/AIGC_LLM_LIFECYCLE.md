# AIGC LLM Lifecycle

Status: `REFERENCE STACK VERIFIED LOCALLY — TRAINING AND SERVING NOT ACTIVATED`

## What is implemented

The AIGC repository now contains a coherent, bounded path from admitted text to a
serving boundary:

1. a closed JSON configuration and schema;
2. a lossless UTF-8 byte tokenizer;
3. deterministic next-token dataset windows;
4. an optional PyTorch causal transformer with tied embeddings and causal attention;
5. bounded pretraining/SFT epoch adapters and a DPO objective;
6. a deterministic lifecycle orchestrator and receipt;
7. a disabled-by-default FastAPI generation boundary; and
8. a read-only MCP/plugin tool for inspecting the lifecycle plan.

The committed configuration has a zero-dollar, zero-GPU-hour resource envelope.
Every training stage is disabled. The lifecycle receipt reports zero training
steps, zero provider calls, zero external actions, no authority, and no production
readiness.

## Corrections to the initial scaffold

The reference implementation does not describe a character lookup as BPE, rely on
undefined global model state, permit unbounded generation, or call an empty RLHF
stub complete. It adds causal attention, length and temperature limits, dimension
validation, finite-loss checks, gradient clipping, dataset sample limits, optional
dependency isolation, schema validation, and an explicit runtime injection
boundary.

The byte tokenizer is intentionally named for what it is. It is deterministic and
lossless, but it is not a production-trained BPE tokenizer. PPO-style RLHF remains
a declared, unexecuted option; DPO has a reference loss implementation. Training a
foundation model, admitting a real corpus, evaluating a checkpoint, and deploying
an authenticated scalable service require separate evidence and authorization.

## Local validation

```bash
.venv/bin/python scripts/validate_aigc_llm_stack.py \
  --output reports/artifacts/aigc_llm_lifecycle_local_validation.json
.venv/bin/python -m pytest -q tests/test_llm_stack.py \
  tests/test_nexus_mcp_contract.py tests/test_aigc_plugin_bridge.py
```

The PyTorch implementation is isolated from the core dependency set. To exercise
it in a separately approved training environment, install
`requirements-llm-training.txt`; importing the ordinary lifecycle package does not
import PyTorch.
