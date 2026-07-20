# AIGC Documentation Index

## Architecture

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — canonical five-plane architecture, authority boundaries, plane ownership, and architectural invariants.
- [`AIGC_OMEGA_PRIME_ENGINEERING_EXECUTION_DIRECTIVE.md`](AIGC_OMEGA_PRIME_ENGINEERING_EXECUTION_DIRECTIVE.md) — master evidence-bound engineering prompt for Codex, ChatGPT, local operation, the ChatGPT app, continuous agents, staging, Canary A, Canary B, and production evidence.
- [`AIGC_OMEGA_PRIME_CODEX_BOOTSTRAP_PROMPT.md`](AIGC_OMEGA_PRIME_CODEX_BOOTSTRAP_PROMPT.md) — concise copy-paste entrypoint that tells Codex to load the complete Ω-Prime contract, refetch live truth, and begin in read-only engineering mode.
- [`CHATGPT_CODEX_REPOSITORY_INTEGRATION.md`](CHATGPT_CODEX_REPOSITORY_INTEGRATION.md) — exact connection path for the GitHub app in ChatGPT, a Codex repository environment, an installable Skill, and a private AIGC MCP app.
- [`CANONICAL_DEPLOYMENT_AND_AUTONOMY_SEQUENCE.md`](CANONICAL_DEPLOYMENT_AND_AUTONOMY_SEQUENCE.md) — contract-backed critical path from hosted-CI recovery through Cloud Run staging, Canary A platform proof, Canary B employer-duty autonomy, and one read-only connector.
- [`CURRENT_REPOSITORY_TRUTH_PROCUREMENT.md`](CURRENT_REPOSITORY_TRUTH_PROCUREMENT.md) — evidence-backed procurement of unresolved completion targets while preserving false safety invariants such as no self-approval, no automatic merge, and no automatic external commitments.
- [`REVIEW_EVIDENCE_PACKET_V1.md`](REVIEW_EVIDENCE_PACKET_V1.md) — review evidence and accountable human judgment.
- [`PRODUCTION_DEPLOYMENT_BASELINE_V1.md`](PRODUCTION_DEPLOYMENT_BASELINE_V1.md) — fail-closed deployment baseline.

## ChatGPT operational acceptance

- [`CHATGPT_OPERATIONAL_ACCEPTANCE_STANDARD.md`](CHATGPT_OPERATIONAL_ACCEPTANCE_STANDARD.md) — definition of evidence-backed `100/100` for a completely functional AIGC application in ChatGPT.
- [`CHATGPT_100_POINT_EXECUTION_CHECKLIST.md`](CHATGPT_100_POINT_EXECUTION_CHECKLIST.md) — attributable execution checklist from local contracts through Developer Mode, hosted CI, staging, Canary A, Canary B, a bounded external action, and final disposition.
- [`../config/chatgpt_operational_readiness.json`](../config/chatgpt_operational_readiness.json) — ten-category weighted readiness ledger and evidence truths.
- [`../src/core/chatgpt_operational_readiness.py`](../src/core/chatgpt_operational_readiness.py) — fail-closed readiness evaluator.

Validate the ChatGPT operational-readiness program with:

```bash
python -m src.core.chatgpt_operational_readiness
pytest -q tests/test_chatgpt_operational_readiness.py
```

A numerical score cannot synthesize missing evidence or grant authority. `release_100_permitted=true` requires every category at `PRODUCTION_ACCEPTED`, every evidence truth true, every safety invariant preserved, and accountable acceptance.

## Reusable engineering Skill

- [`../skills/aigc-omega-prime-engineering/SKILL.md`](../skills/aigc-omega-prime-engineering/SKILL.md) — Agent Skills bundle entrypoint for governed AIGC engineering in ChatGPT, Codex, and compatible agent runtimes.

The Skill must refetch live repository state before using stored revisions and grants no merge, deployment, credential, external-submission, or production authority.

Validate the canonical deployment sequence with:

```bash
python -m src.core.canonical_deployment_sequence
pytest -q tests/test_canonical_deployment_sequence.py
```

Validate the current repository truth-procurement program with:

```bash
python -m src.core.current_repository_truth_procurement
pytest -q tests/test_current_repository_truth_procurement.py
```

The resulting receipts identify the first incomplete stage or truth transition and grant no merge, cloud, credential, submission, communication, scheduling, contract, delivery, payment, or production authority.

## CI diagnosis and recovery

- [`GITHUB_ACTIONS_ZERO_STEP_ROOT_CAUSE.md`](GITHUB_ACTIONS_ZERO_STEP_ROOT_CAUSE.md) — evidence-backed isolation of the hosted-runner zero-step failure, ranked remaining account/repository causes, operator inspection order, remediation branches, and support escalation packet.
- [`../config/github_actions_zero_step_diagnosis.json`](../config/github_actions_zero_step_diagnosis.json) — machine-readable success-to-failure boundary and three-probe diagnosis.
- [`../scripts/collect_github_actions_preflight.py`](../scripts/collect_github_actions_preflight.py) — read-only collector for repository Actions permissions, exact run/job state, check annotations, artifacts, and current public GitHub status.

Run the collector from an authenticated checkout:

```bash
python scripts/collect_github_actions_preflight.py
```

The collector requires `GH_TOKEN` or `GITHUB_TOKEN` with repository **Administration: read** and **Actions: read** permissions. Add **Checks: read** to retrieve check-run annotations for final cause attribution. A classic token may use the repository `repo` scope. The collector performs GET requests only, never records the token, and writes:

```text
reports/artifacts/governance/github-actions-zero-step-live-diagnosis.json
```

Validate the committed diagnosis and classifier with:

```bash
pytest -q tests/test_github_actions_zero_step_diagnosis.py
```

The current diagnosis is a runner-allocation/account-or-repository eligibility block. No repository command executed in the zero-step runs, so Python, Terraform, tests, checkout and artifact upload are downstream rather than primary causes.

## Staging preparation

- [`STAGING_BOOTSTRAP.md`](STAGING_BOOTSTRAP.md) — mock-only staging preparation runbook.
- [`CLOUD_SQL_STAGING_FOUNDATION.md`](CLOUD_SQL_STAGING_FOUNDATION.md) — private-IP Cloud SQL Terraform module, gates, validation, and operational-evidence requirements.
- [`governance/evolution/AIGC_PROVIDER_DISCOVERY_AUTOMATION_KIT_V1.md`](governance/evolution/AIGC_PROVIDER_DISCOVERY_AUTOMATION_KIT_V1.md) — provider-discovery command and simulation boundary.
- [`governance/evolution/AIGC_STAGING_PROCUREMENT_STATE_MACHINE_V1_1.md`](governance/evolution/AIGC_STAGING_PROCUREMENT_STATE_MACHINE_V1_1.md) — exact staging procurement state machine.

Run the current preparation surface with:

```bash
bash scripts/bootstrap-staging.sh
```

The command is revision-bound and mock-only. It stops before live provider discovery authorization and performs no external action.

Validate the inert Terraform definitions with:

```bash
terraform -chdir=infra/terraform/gcp fmt -check -recursive
terraform -chdir=infra/terraform/gcp init -backend=false
terraform -chdir=infra/terraform/gcp validate
```

The committed Terraform example keeps resource and subsystem authority disabled.

## Runtime truth

The operator API endpoint:

```text
GET /api/v1/readiness
```

returns:

- current ledger-derived structural readiness;
- current production blockers;
- a separately labeled evidence-complete projection;
- delivery-judgment implementation status;
- the highest-impact next step.

Projected readiness never grants authority or changes the canonical production-ready state.
