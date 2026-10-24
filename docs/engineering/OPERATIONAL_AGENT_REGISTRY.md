# AIGC Operational Agent Registry v1

This branch adds a local agent registry and dispatcher. The registry routes named phase agents through existing governed AIGC phase commands and provides seven deterministic engineering workflow planners. It does not claim every agent is an independent LLM.

## Usage

- List agents: `python src/aigc_agents.py list`
- Inspect an agent: `python src/aigc_agents.py inspect opportunity_radar`
- Run a phase adapter: `python src/aigc_agents.py run runtime_preflight`
- Create a workflow plan: `python src/aigc_agents.py run root_cause --task "Diagnose duplicate task delivery"`
- Write a plan artifact: add `--output data/agents/runs/plan.json`

Phase agents delegate to the existing `src/aigc.py run <phase>` path and do not gain extra permissions. Emergency-stop and phase-specific authorization controls remain in effect. External actions are not enabled by this registry.

Workflow planner IDs: `root_cause`, `zero_regression_refactor`, `adversarial_testing`, `contract_synthesis`, `architecture_tradeoff`, `legacy_reverse_engineering`, `red_team_review`.

The workflow planners are deterministic plan generators, not model-backed autonomous engineering agents. They do not inspect repositories, edit code, run tests, or claim defects are fixed. If `--output` is used, the artifact includes the task text; do not include secrets or personal data. Runtime audit records store only a SHA-256 digest of the task.

Before model-backed execution is enabled, implement and test a provider adapter, structured output validation, input isolation, independent policy enforcement, per-agent capability grants, timeout/retry/cancellation, redacted telemetry, persistence/idempotency, and human approval for write-enabled modes.
