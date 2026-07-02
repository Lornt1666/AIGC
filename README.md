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
python .\src\aigc.py run pipeline --mode synthetic
python .\src\aigc.py run pipeline --mode real_data_read_only --source remoteok --limit 10
python .\src\aigc.py emergency-stop
python .\src\aigc.py clear-emergency-stop
```

Phase 14 is an internal runtime preflight. It does not perform external actions.

Scoped approval packet decisions can be recorded internally only with exact phrases:

```powershell
python .\src\aigc.py approve --action-id AIGC-ACT-... --phrase "I, Justice Gray Maciocha, accept action AIGC-ACT-...."
python .\src\aigc.py deny --action-id AIGC-ACT-... --phrase "I, Justice Gray Maciocha, deny action AIGC-ACT-...."
```

Approving a packet authorizes Phase 6 eligibility only. It does not send, submit, message, bid, or perform external execution.

## Milestone B Security Hardening

Milestone B adds stronger local security controls:

- Real secret-scanner CLI with nonzero exit on findings.
- Hash-stored approval tokens for approval-required secret access.
- Internal incident-response stubs.
- GitHub Actions validation workflow.
- Branch-protection scripts for use after `gh auth login`.

Commands:

```powershell
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md OMEGA_X_CONSTITUTION.md schemas tests reports
python .\src\aigc.py issue-approval-token --scope secret:OPENAI_API_KEY --phase phase4_proposal_drafting --reason "approved internal test"
python -m pytest
```

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
