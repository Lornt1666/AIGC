# AIGC MVP Kernel

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

This project implements the internal-only AIGC MVP kernel.

Phase 2 is a read-only opportunity radar. It reads approved API/RSS/public feed sources, normalizes records, classifies them, filters unsafe targets, scores radar fit, and writes an opportunity queue.

Phase 3 is an internal ology assessment engine. It reads the Phase 2 queue and produces assessment dossiers. It does not apply, message, bid, submit, use credentials, or contact employers.

Phase 4 drafts professional proposal packages. Phase 5 creates scoped authorization packets. Phase 6 creates exact-action execution receipts or manual handoffs only for approved packets. Phase 7 builds employer-safe audit packet drafts. Phase 8 records outcomes and proposes governed improvements.

Omega-X supervises local memory and evolution patches. Phase 11 provides a secrets-vault scaffold that stores only secret references in the repo.

## Run Phase 2

```powershell
python .\src\phase2_radar.py
```

Outputs:

- `data/phase2_raw/raw_weworkremotely.json`
- `data/phase2_raw/raw_remoteok.json`
- `data/phase2_raw/raw_remotive.json`
- `data/phase2_raw/raw_github.json`
- `data/phase2_processed/aigc_phase2_opportunity_queue.json`
- `data/audit/aigc_phase2_audit.jsonl`
- `data/reports/phase2_signature_update.md`

## Run Phase 3

```powershell
python .\src\phase3_ology_assessment.py
```

Outputs:

- `data/phase3_processed/aigc_phase3_assessment_dossiers.json`
- `data/audit/aigc_phase3_audit.jsonl`
- `data/reports/phase3_signature_update.md`

## Run Phase 4

```powershell
python .\src\phase4_proposal_drafting.py
```

Outputs:

- `data/phase4_proposals/aigc_phase4_proposal_packages.json`
- `data/audit/aigc_phase4_audit.jsonl`
- `data/reports/phase4_signature_update.md`

## Run Phase 5

```powershell
python .\src\phase5_human_approval_gate.py
```

Outputs:

- `data/phase5_authorizations/aigc_phase5_authorization_packets.json`
- `data/audit/aigc_phase5_audit.jsonl`
- `data/reports/phase5_signature_update.md`

## Run Phase 6

```powershell
python .\src\phase6_controlled_execution.py
```

Outputs:

- `data/phase6_execution/aigc_phase6_execution_receipts.json`
- `data/audit/aigc_phase6_audit.jsonl`
- `data/reports/phase6_signature_update.md`

Phase 6 only processes packets already marked `approved_for_phase_6`. Pending packets produce no execution receipts.

## Run Phase 7

```powershell
python .\src\phase7_employer_audit_packet.py
```

Outputs:

- `data/phase7_audit_packets/aigc_phase7_employer_audit_packets.json`
- `data/audit/aigc_phase7_audit.jsonl`
- `data/reports/phase7_signature_update.md`

Phase 7 creates internal employer-safe audit packet drafts. It does not share them externally.

## Run Phase 8

```powershell
python .\src\phase8_evolution_loop.py
```

Outputs:

- `data/phase8_evolution/outcome_records.jsonl`
- `data/phase8_evolution/agent_performance.jsonl`
- `data/phase8_evolution/evolution_cycle_reports.jsonl`
- `data/phase8_evolution/evolution_patches.jsonl`
- `data/phase8_evolution/next_cycle_strategy.json`
- `data/reports/phase8_signature_update.md`

Phase 8 records internal outcomes and proposes patches. Behavior-changing patches require explicit operator approval.

## Run Omega-X

```powershell
python .\src\omega_x_orchestrator.py
```

Outputs:

- `memory/omega_x/memory/omega_memory.sqlite`
- `memory/omega_x/memory/omega_events.jsonl`

Omega-X supervises local memory and patch records. The default config does not write into the separate `AIGC_MEMORY_CORE` folder.

## Phase 11 Secrets Scaffold

Secret values must not be stored in this repo. Store only references in `config/secret_manifest.json`.

The `src/security` modules provide:

- Google Cloud Secret Manager client wrapper with lazy dependency import.
- Secret Broker with phase/agent/approval policy checks.
- Secret audit ledger that never logs secret values.
- Redactor for secret-like text.

Live secret retrieval is disabled by default in `SecretBroker`.

Run Phase 11 manifest validation and fake-secret verification:

```powershell
python .\src\phase11_security_vault.py --fake-test
```

Outputs:

- `data/audit/phase11_secret_access_log.jsonl`
- `data/reports/phase11_signature_update.md`

The external-drive secret map is stored at:

- `C:\Users\Justice Gray Macioch\AIGC_MEMORY_CORE\config\secret_manifest.json`

The Google Cloud setup runbook is:

- `docs/google_secret_manager_setup.md`

Build a non-executing Google Cloud Secret Manager command plan:

```powershell
python .\src\security\google_secret_manager_provisioning.py --project-id YOUR_PROJECT_ID --member "user:YOUR_EMAIL@example.com"
```

Output:

- `data/phase11_security/google_secret_manager_command_plan.json`

This only writes a plan. It does not create Google Cloud resources.

## Run Phase 12

```powershell
python .\src\phase12_observability_dashboard.py --export
```

Outputs:

- `data/phase12_observability/system_snapshot.json`
- `reports/phase12_system_health.md`

Optional local UI:

```powershell
streamlit run .\src\dashboard\local_observability_app.py
```

## Run Phase 13

Synthetic non-production sandbox:

```powershell
python .\src\phase13_simulation_arena.py
```

Real public read-only replay:

```powershell
python .\src\phase13_real_data_replay.py --source remoteok --limit 10
```

Allowed real replay sources:

- `remoteok`
- `remotive`
- `weworkremotely`
- `github_issues`

Outputs:

- `data/phase13_simulation/synthetic_simulation_result.json`
- `data/phase13_real_data_replay/latest_real_data_replay.json`
- `reports/phase13_synthetic_simulation_report.md`
- `reports/phase13_real_data_replay_report.md`

Phase 13B retrieves real public/API/RSS data in read-only mode and stops before any external action.

## Milestone A Kernel CLI

Milestone A adds a contract-first local runtime surface:

- `schemas/` contains JSON contracts for core phase artifacts.
- `src/core/contract_validator.py` validates artifacts before downstream use.
- `src/core/state_store.py` initializes `memory/aigc_state.sqlite`.
- `src/core/phase_registry.py` maps phase inputs, outputs, schemas, commands, modes, and risk.
- `src/aigc.py` provides the unified CLI.

Commands:

```powershell
python .\src\aigc.py init-db
python .\src\aigc.py status
python .\src\aigc.py validate
python .\src\aigc.py run phase12
python .\src\aigc.py run phase13
python .\src\aigc.py run phase14
python .\src\aigc.py run phase15
python .\src\aigc.py run phase16
python .\src\aigc.py run phase17
python .\src\aigc.py run phase22
python .\src\aigc.py run phase23
python .\src\aigc.py run phase24
python .\src\aigc.py run phase25
python .\src\aigc.py run pipeline --mode synthetic
python .\src\aigc.py run pipeline --mode real_data_read_only --source remoteok --limit 10
python .\src\aigc.py close-loop --execution-mode manual_handoff
python .\src\aigc.py emergency-stop
python .\src\aigc.py clear-emergency-stop
```

Phase 14 is an internal runtime preflight. It does not perform external actions.

Scoped approval packet decisions can be recorded internally only with exact phrases:

```powershell
python .\src\aigc.py approve --action-id AIGC-ACT-... --phrase "I, Justice Gray Maciocha, accept action AIGC-ACT-...."
python .\src\aigc.py deny --action-id AIGC-ACT-... --phrase "I, Justice Gray Maciocha, deny action AIGC-ACT-...."
python .\src\aigc.py revise --action-id AIGC-ACT-... --phrase "Revise action AIGC-ACT-...: revision instructions"
```

Approving a packet authorizes Phase 6 eligibility only. It does not send, submit, message, bid, or perform external execution.

Expired authorization packets cannot be approved through the CLI. Regenerate Phase 5 packets before approving expired actions.

Milestone C closes the internal loop from approved Phase 5 packets into Phase 6 manual handoffs or dry runs, then Phase 7 internal audit drafts:

```powershell
python .\src\aigc.py close-loop --execution-mode dry_run
python .\src\aigc.py close-loop --execution-mode manual_handoff
```

Outputs:

- `data/phase14_pipeline_closure/latest_pipeline_closure.json`
- `reports/milestone_c_pipeline_closure_report.md`

The closure runner does not approve actions, contact recipients, use credentials, or perform external execution.

## Milestone E Connector Maturity

Milestone E adds Phase 10 as a connector governance layer. It converts configured discovery sources into connector capability records and blocks unsafe drift before any connector can become live.

Command:

```powershell
python .\src\aigc.py run phase10
```

Outputs:

- `data/phase10_connectors/aigc_phase10_connector_registry.json`
- `data/reports/phase10_signature_update.md`
- `data/audit/aigc_phase10_audit.jsonl`
- `reports/milestone_e_connector_maturity_report.md`

Phase 10 is read-only governance only. It does not enable live write connectors, use credentials, apply to jobs, message employers, submit deliverables, bid, upload files, or perform external execution.

## Milestone F Productization Readiness

Milestone F adds Phase 18 as an internal productization readiness layer. It verifies release-critical files, confirms the All Rights Reserved notice, and produces a private release-readiness manifest.

Command:

```powershell
python .\src\aigc.py run phase18
```

Outputs:

- `data/phase18_productization/aigc_phase18_release_readiness.json`
- `data/reports/phase18_signature_update.md`
- `data/audit/aigc_phase18_audit.jsonl`
- `reports/milestone_f_productization_report.md`
- `docs/PRODUCTIZATION_RUNBOOK.md`

Phase 18 does not deploy, publish, distribute, enable live connectors, use credentials, contact employers, submit applications, or perform external execution.

## Milestone G Sub-Agent Generation Forge

Milestone G adds Phase 19 as an internal specialist-team planning layer. It turns eligible proposal packages into governed sub-agent team plans with explicit roles, input contracts, output contracts, allowed actions, forbidden actions, quality criteria, and handoff targets.

Command:

```powershell
python .\src\aigc.py run phase19
```

Outputs:

- `data/phase19_subagents/aigc_phase19_subagent_team_plans.json`
- `data/reports/phase19_signature_update.md`
- `data/audit/aigc_phase19_audit.jsonl`
- `reports/milestone_g_subagent_forge_report.md`

Phase 19 does not create autonomous external actors. Generated sub-agents are internal planning records only and cannot contact employers, submit applications, open pull requests, post comments, bid, use credentials, or bypass approval gates.

## Milestone H Fidelity Forge

Milestone H adds Phase 20 as an internal quality, traceability, and readiness review layer. It reviews eligible proposal packages, Phase 19 sub-agent team plans, and Phase 16 compliance records before anything can be considered for external approval.

Command:

```powershell
python .\src\aigc.py run phase20
```

Outputs:

- `data/phase20_fidelity/aigc_phase20_fidelity_reviews.json`
- `data/reports/phase20_signature_update.md`
- `data/audit/aigc_phase20_audit.jsonl`
- `reports/milestone_h_fidelity_forge_report.md`

Phase 20 does not approve actions, contact employers, submit applications, submit deliverables, open pull requests, post comments, bid, use credentials, or bypass Phase 5. It only produces internal fidelity review records and revision recommendations.

## Milestone I Customer Satisfaction Continuum

Milestone I adds Phase 21 as an internal Customer Happiness Index layer. It scores expected customer satisfaction before any external action using proposal quality, fidelity reviews, compliance posture, finance blockers, and Phase 5 approval state.

Command:

```powershell
python .\src\aigc.py run phase21
```

Outputs:

- `data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json`
- `data/reports/phase21_signature_update.md`
- `data/audit/aigc_phase21_audit.jsonl`
- `reports/milestone_i_customer_satisfaction_report.md`

Phase 21 does not contact customers, promise outcomes, accept contracts, request payment, submit deliverables, or bypass approval gates. CHI is an internal estimate until real employer response, delivery, and revision outcomes exist.

## Milestone J Quantum-Aware Quality Kernel

Milestone J adds Phase 22 as an internal quality-state, ology, and uncertainty-aware review layer. It applies the Proto-Omni Perfection Cycle to governed AIGC artifacts so the worker can recognize work quality, surface uncertainty, and produce improvement directives before any external action.

Command:

```powershell
python .\src\aigc.py run phase22
```

Outputs:

- `data/phase22_quality/aigc_phase22_quality_kernel_records.json`
- `data/reports/phase22_signature_update.md`
- `data/audit/aigc_phase22_audit.jsonl`
- `reports/milestone_j_quantum_quality_kernel_report.md`

Quantum-aware means deterministic uncertainty-aware quality-state modeling. Phase 22 does not claim literal quantum cognition, approve actions, contact customers, accept contracts, use credentials, submit work, or bypass legal, ethical, compliance, security, and Phase 5 approval gates.

## Milestone K Ascended Work Order Governor

Milestone K adds Phase 23 as an internal work-order quality application layer. It consumes Phase 22 quality-kernel records and forces each governed work order through `Perfect Draft v1`, `Ontological Self-Audit`, and `Ascended Output v2`.

Command:

```powershell
python .\src\aigc.py run phase23
```

Outputs:

- `data/phase23_work_orders/aigc_phase23_work_order_governance_records.json`
- `data/reports/phase23_signature_update.md`
- `data/audit/aigc_phase23_audit.jsonl`
- `reports/milestone_k_work_order_governor_report.md`

Phase 23 applies the quality doctrine to work orders, but it still performs no external action. It does not approve work, contact customers, submit applications, submit deliverables, accept contracts, request payment, use credentials, or bypass Phase 5 and Phase 6 gates.

## Milestone L Truth-First Procurement Governance

Milestone L adds Phase 24 as an internal procurement truth ledger. It classifies each work candidate by source truth, generated-artifact status, Phase 5 approval state, stale or expired status, and cleanup recommendation.

Command:

```powershell
python .\src\aigc.py run phase24
```

Outputs:

- `data/phase24_procurement/aigc_phase24_procurement_records.json`
- `data/reports/phase24_signature_update.md`
- `data/audit/aigc_phase24_audit.jsonl`
- `reports/milestone_l_procurement_governance_report.md`

Phase 24 preserves real read-only source snapshots as evidence and marks Phase 4+ artifacts as generated internal derivatives. Expired pending Phase 5 packets are classified as stale generated action candidates that should be archived or regenerated before any future approval attempt.

Phase 24 does not delete files, approve actions, contact external parties, submit applications, submit proposals, submit deliverables, accept contracts, request payment, use credentials, or bypass Phase 5 and Phase 6 gates.

## Milestone M Continuous Intelligence Ingestion Layer

Milestone M adds Phase 25 as an internal freshness, drift, and knowledge-update ledger. It monitors configured local artifacts, validates timestamps and record counts, detects stale generated candidates, and emits refresh or regeneration targets.

Command:

```powershell
python .\src\aigc.py run phase25
```

Outputs:

- `data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json`
- `data/reports/phase25_signature_update.md`
- `data/audit/aigc_phase25_audit.jsonl`
- `reports/milestone_m_continuous_intelligence_ingestion_report.md`

Phase 25 implements the Continuous Intelligence Ingestion Layer as an operator-scheduled internal refresh cycle. It does not run as a background daemon and does not fetch external data by itself. External data procurement remains governed by explicit operator command, connector policy, source permissions, and approval gates.

Phase 25 does not delete stale artifacts, approve actions, contact external parties, submit applications, submit proposals, submit deliverables, accept contracts, request payment, use credentials, or bypass Phase 5 and Phase 6 gates.

## Milestone D Finance, Compliance, and Incident Response

Milestone D adds internal-only controls for finance tracking, compliance screening, and incident response readiness.

Commands:

```powershell
python .\src\aigc.py run phase15
python .\src\aigc.py run phase16
python .\src\aigc.py run phase17
python .\src\aigc.py create-incident --incident-type prompt_injection --severity medium --summary "Suspicious listing instructions detected."
```

Outputs:

- `data/phase15_finance/aigc_phase15_finance_ledger.json`
- `data/phase16_compliance/aigc_phase16_compliance_reviews.json`
- `data/phase17_incidents/incident_response_summary.json`
- `data/phase17_incidents/incident_reports.jsonl`
- `reports/phase17_incident_response_report.md`
- `data/reports/phase15_signature_update.md`
- `data/reports/phase16_signature_update.md`

Phase 15 does not accept contracts, send invoices, request payment, or make tax/legal claims.
Phase 16 does not provide legal advice or approve regulated work.
Phase 17 creates internal incident records only and does not notify external parties.

## Milestone B Security Hardening

Milestone B adds stronger local security controls:

- Real secret-scanner CLI with nonzero exit on findings.
- Hash-stored approval tokens for approval-required secret access.
- Internal incident-response stubs.
- GitHub Actions validation workflow.
- Branch-protection scripts for use after `gh auth login`.
- Local Git guards for private-repo branch discipline while GitHub branch protection is unavailable.

Commands:

```powershell
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md OMEGA_X_CONSTITUTION.md schemas tests reports
python .\src\aigc.py issue-approval-token --scope secret:OPENAI_API_KEY --phase phase4_proposal_drafting --reason "approved internal test"
python -m pytest
```

Install local Git guards:

```powershell
.\scripts\install_local_git_guards.ps1
```

Daily private-repo workflow:

```powershell
git switch main
git pull --ff-only
git switch -c codex/my-change
git push -u origin codex/my-change
gh pr create --draft --base main --head codex/my-change --title "[codex] my change"
```

See `docs/PRIVATE_BRANCH_WORKFLOW.md` for the full branch discipline policy.

Apply GitHub branch protection only after authenticating:

```powershell
gh auth login
.\scripts\apply_github_branch_protection.ps1 -Owner Lornt1666 -RepoName AIGC -Branch main
```

## Publish Private GitHub Repo

Authenticate first:

```powershell
gh auth login
```

Then publish:

```powershell
.\scripts\create_private_github_repo_gh.ps1 -Owner Lornt1666 -RepoName AIGC
```

The repository includes an All Rights Reserved license notice in `LICENSE`, `README.md`, and `AGENTS.md`.

## Safety Boundary

Allowed:

- Read approved sources.
- Normalize, classify, score, assess.
- Write internal reports and audit logs.
- Draft proposals internally.
- Create approval packets.
- Create manual handoff instructions for approved packets.
- Generate employer-safe audit drafts internally.
- Record internal memory and evolution reports.

Blocked:

- Apply.
- Message.
- Bid.
- Submit proposals or deliverables.
- Use credentials.
- Use operator identity externally.
- Scrape prohibited websites.
- Bypass platform restrictions.
- Store raw credentials.
- Share employer audit packets externally without approval.
- Apply behavior-changing evolution patches without approval.
