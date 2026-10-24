# AIGC Operational Agent Registry v1

This branch adds a local agent registry and dispatcher. The registry contains 24 phase adapters and 21 deterministic workflow planners: 14 project-domain planners and seven engineering workflow planners. Phase adapters delegate to existing governed AIGC phase commands; workflow planners produce structured plans. Neither category is automatically an independent model-backed autonomous agent.

## Usage

- List agents: `python src/aigc_agents.py list`
- Inspect an agent: `python src/aigc_agents.py inspect opportunity_radar`
- Run a phase adapter: `python src/aigc_agents.py run runtime_preflight`
- Create a workflow plan: `python src/aigc_agents.py run root_cause --task "Diagnose duplicate task delivery"`
- Write a plan artifact: add `--output data/agents/runs/plan.json`

Phase agents delegate to the existing `src/aigc.py run <phase>` path and do not gain extra permissions. Emergency-stop and phase-specific authorization controls remain in effect. External actions are not enabled by this registry.

**Engineering workflow planner IDs (7):** `root_cause`, `zero_regression_refactor`, `adversarial_testing`, `contract_synthesis`, `architecture_tradeoff`, `legacy_reverse_engineering`, `red_team_review`.

**Project-domain planner IDs (14):** `aigc_architecture`, `job_enquiry_application`, `mobile_gateway`, `cloud_orchestration`, `google_execution_adapter`, `regenexcalibur_envelope`, `carbon_capture_mrv`, `fabrication_safety`, `protocol_governance`, `security_privacy`, `release_assurance`, `gemini_xprize`, `data_analytics`, `ci_diagnostics`.

The registry-count test is intended to keep this inventory synchronized with the implementation.

The workflow planners are deterministic plan generators, not model-backed autonomous engineering agents. They do not inspect repositories, edit code, run tests, or claim defects are fixed. If `--output` is used, the artifact includes the task text; do not include secrets or personal data. Runtime audit records store only a SHA-256 digest of the task.

Before model-backed execution is enabled, implement and test a provider adapter, structured output validation, input isolation, independent policy enforcement, per-agent capability grants, timeout/retry/cancellation, redacted telemetry, persistence/idempotency, and human approval for write-enabled modes.
