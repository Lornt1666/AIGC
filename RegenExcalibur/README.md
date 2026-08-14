# RegenExcalibur OS

RegenExcalibur is the governed universe-planning layer of AIGC. It turns a validated seed into deterministic ontology, architecture, engineering, security, observability, and evolution artifacts. The mythic vocabulary is a stable product language; every name maps to a concrete typed mechanism.

## Executable contract

| Universe term | Repository mechanism |
|---|---|
| Prime Kernel | `src/regenexcalibur/orchestrator.py` |
| Agent Forge | fixed descriptors in `agent_forge.py`; no hidden process spawning |
| LIFE Beacon | fail-closed request and recursion policy in `life_beacon.py` |
| Design Crucible / Engineering Loom | deterministic stages and typed artifact contracts |
| Pipeline Serpent | repository CI, verification, security, and recovery gates |
| Evolution Spire | bounded proposal generation; no self-modification |
| Universe Gate | `aigc_seed_regenexcalibur_universe` MCP/bridge operation |

The Gate is zero-egress and plan-only. A `PASS` proves that a local blueprint and its receipt validated. It does not prove deployment, provider connectivity, public availability, funding, legal approval, or production readiness.

## Local use

```bash
.venv/bin/python scripts/validate_regenexcalibur_universe.py
printf '%s' '{"operation":"aigc_seed_regenexcalibur_universe","arguments":{"requested_evolution_depth":1}}' \
  | .venv/bin/python -m src.integrations.aigc_plugin_bridge
```

The canonical seed is `config/regenexcalibur_universe_seed.v1.json`. The reusable coordination contract is in `prompts/llm-agent-coordination-1jgm.md`.

## Authority boundary

RegenExcalibur may locally parse, design, validate, simulate, test, hash, and prepare reviewable patches. It may not infer permission to purchase hosting, call a model provider, contact a person, publish an app, spend funds, deploy production workloads, transfer intellectual property, or transact on a mainnet. Each such action requires the AIGC Phase 5 gate and a server-side one-use permit bound to the exact actor, destination, payload, cost ceiling, expiry, and immutable resource identity.
