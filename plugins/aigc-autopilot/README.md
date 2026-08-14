# AIGC Autopilot MCP

Status: `LOCAL STREAMABLE HTTP VERIFIED — CHATGPT HOST AND PUBLIC DEPLOYMENT NOT PERFORMED`

This directory is the canonical distribution entrypoint for the portable AIGC MCP facade. The implementation remains in the governed Python core so every client receives the same structured truth without depending on a custom widget.

## Canonical tools

| Tool | Effect |
|---|---|
| `aigc_get_status` | Sanitized read-only connector, occupation-pack and runtime status |
| `aigc_render_control_center` | Structured control-center projection; a widget is optional |
| `assess_aigc_action` | Classify consequence and required authority without granting either |
| `run_aigc_dry_run` | Simulate a work-search, application, communication, or daily-work workflow and stop before execution |
| `procure_deep_research_plan` | Build a source-governed research plan without retrieval, provider dispatch, or spend |
| `aigc_run_employer_sandbox` | Deterministic zero-egress employer fixture with a canonical receipt |
| `aigc_seed_regenexcalibur_universe` | Validate the 1JGM Genesis seed and emit a bounded zero-egress universe receipt |
| `aigc_plan_wealth_work` | Plan governed opportunity, deliverable, sales, revenue, invoice and transaction work without performing the consequential action |
| `aigc_plan_llm_lifecycle` | Validate and coordinate the canonical data-to-serving lifecycle without training, provider calls, spend, deployment, or activation |
| `aigc_plan_regenexcalibur_workflow` | Prepare affix-tagged job, employer-practice, work-delivery, or invoice workflows without external execution |
| `aigc_run_regenexcalibur_diagnostics` | Run the six isolated blocked-action fixtures and emit an audit-bound acceptance report |

The wealth operator permits public zero-cost research and local reversible preparation. Recording revenue, submitting applications, sending outreach or invoices, accepting contracts, spending or transferring funds, placing trades and executing transactions remain request-bound approval gates. The LLM lifecycle tool validates a reproducible reference stack but deliberately cannot start training or serving. No live provider adapter, credential operation, cloud mutation, message, application submission, billing mutation or production activation is exposed through this facade.

## Run

```bash
.venv/bin/python -m src.integrations.mcp.server --transport streamable-http --host 127.0.0.1 --port 8000
```

The endpoint is `http://127.0.0.1:8000/mcp`. Keep it on loopback until an authenticated, separately authorized HTTPS deployment exists.

Fixed JSON bridge example:

```bash
printf '%s' '{"operation":"aigc_run_employer_sandbox","arguments":{"mode":"sandbox"}}' \
  | .venv/bin/python -m src.integrations.aigc_plugin_bridge
```

Acceptance requires:

- `external_actions_performed == 0`;
- `provider_calls_performed == 0`;
- a valid `receipt_sha256`;
- explicit terminal status;
- no credential or secret material.

The ChatGPT host connection, Gemini client validation, authenticated cloud deployment, public plugin publication and any live employment action are separate evidence and authority boundaries.
