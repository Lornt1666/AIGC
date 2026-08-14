# AIGC Nexus MCP Plugin

Status: `LOCAL READ/SIMULATE FACADE VERIFIED — HOST CONNECTION NOT PERFORMED`

## Purpose and archetype

`aigc-nexus` is a provider-neutral, tool-only MCP server. It deliberately starts
without an embedded widget so ChatGPT, supported Gemini developer surfaces, MCP
Inspector, and later standalone clients can use the same model-readable results.
The server never treats a client confirmation, prompt, memory, or caller boolean
as execution authority.

This follows current OpenAI guidance to build focused tools first and add optional
UI only after the server works without it:

- <https://developers.openai.com/plugins/build/mcp-server>
- <https://developers.openai.com/plugins/concepts/mcp-server>
- <https://developers.openai.com/plugins/deploy/connect-chatgpt>

## Tool contract

| Tool | Purpose | External effect |
|---|---|---|
| `aigc_get_status` | Return sanitized system, connector, and occupation-pack truth | None |
| `aigc_render_control_center` | Return a structured, widget-independent control-center projection | None |
| `assess_aigc_action` | Classify consequence and required authority | None; cannot accept a permit or caller-asserted authority |
| `run_aigc_dry_run` | Simulate work search, application preparation, communication, or daily work | None; always stops before `EXECUTE` |
| `procure_deep_research_plan` | Create a decision-bound source, challenge, synthesis, and verification plan | None; stops before source retrieval or provider dispatch |
| `aigc_run_employer_sandbox` | Exercise one declared capability against deterministic fixtures | None; emits a canonical receipt and denies adversarial/regulated scenarios |
| `aigc_seed_regenexcalibur_universe` | Validate the canonical 1JGM seed and synthesize the bounded Genesis plan | None; emits a deterministic zero-egress receipt and never self-modifies |
| `aigc_plan_regenexcalibur_workflow` | Prepare an affix-tagged job, employer-practice, delivery, or invoice workflow | None; produces a plan and stops before external execution |
| `aigc_run_regenexcalibur_diagnostics` | Run the six deterministic blocked-action diagnostic fixtures | None; emits a local audit-bound acceptance report |
| `aigc_plan_wealth_work` | Coordinate bounded wealth-work planning | None; consequential financial and external actions remain approval-gated |
| `aigc_plan_llm_lifecycle` | Validate and coordinate the canonical data-to-serving LLM lifecycle | None; no training, provider call, spend, deployment, or activation |

All eleven tools advertise:

```text
readOnlyHint    = true
destructiveHint = false
idempotentHint  = true
openWorldHint   = false
```

Every result contains model-readable content and structured content. Safe result
objects explicitly state `authority_granted=false` and
`external_action_performed=false`. No tool reads credentials, Gmail, Indeed,
employer sites, cloud services, or provider billing.

## Local operation

Install the exact requirements, then run stdio for a local MCP client:

```bash
.venv/bin/python -m src.integrations.mcp.server --transport stdio
```

Run a loopback Streamable HTTP endpoint:

```bash
.venv/bin/python -m src.integrations.mcp.server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8000
```

The MCP URL is `http://127.0.0.1:8000/mcp`. Keep it on loopback unless a
separately approved private tunnel or authenticated hosting boundary exists.

Inspect locally with MCP Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

Select Streamable HTTP and enter `http://127.0.0.1:8000/mcp`.

## ChatGPT developer-mode test

This repository does not create a public endpoint or a tunnel automatically.
When an approved private test connection exists:

1. Run the local server.
2. Connect it using OpenAI Secure MCP Tunnel or an approved HTTPS test endpoint.
3. In ChatGPT, enable Developer mode under Settings → Security and login.
4. Add a plugin connection with the complete `/mcp` URL or selected tunnel.
5. Review the eleven discovered tools and their annotations.
6. Test direct, indirect, follow-up, malformed, and unsupported prompts.
7. Verify every execution request remains blocked and refresh metadata after a change.

Developer-mode availability and tunnel access depend on the account and workspace.
Public plugin submission additionally requires a public production HTTPS endpoint
and separate review; neither is claimed here.

## Gemini developer configuration

`config/gemini-mcp.example.json` is a least-privilege stdio example. Replace the
two absolute paths locally, retain `trust:false`, and retain the exact
`includeTools` allowlist. The configuration is intended for Gemini CLI or another
official developer surface that supports MCP. It is not evidence that the consumer
Gemini web application supports this custom plugin or UI.

## Occupation packs and research procurement

Thirteen packs are in `config/occupation_packs/`; the complete catalogue and its
official classification basis are documented in
`docs/architecture/AIGC_OCCUPATION_PACKS_AND_DEEP_RESEARCH.md`. They are `DRAFT`,
`LOCAL_DRAFT_ONLY`, require training rights and human review, exclude regulated or
legally consequential actions, and cannot self-certify.

`procure_deep_research_plan` applies the closed policy in
`config/aigc_deep_research_policy.v1.json`. It returns planned queries, source
tiers, quality gates, current provider-contract references, and the first blocker.
It performs zero provider calls and zero source retrieval.

## Verification

```bash
.venv/bin/python scripts/validate_aigc_occupation_packs.py
.venv/bin/python scripts/validate_aigc_deep_research_policy.py
.venv/bin/python scripts/validate_aigc_universal_integration.py
.venv/bin/python scripts/validate_regenexcalibur_universe.py
.venv/bin/python scripts/validate_aigc_llm_stack.py
.venv/bin/python -m pytest -q tests/test_nexus_mcp_contract.py \
  tests/test_nexus_occupation_packs.py \
  tests/test_nexus_deep_research_procurement.py
```

The local verification ladder reaches:

- Level 0: exact tool, schema, authority, and repository-shape review;
- Level 1: Python compilation and unit/adversarial tests;
- Level 2: real Streamable HTTP initialization, tool discovery, and tool call.

Level 3 host-loop validation in ChatGPT/Gemini and any hosted deployment remain
unperformed and must not be inferred from local success.
