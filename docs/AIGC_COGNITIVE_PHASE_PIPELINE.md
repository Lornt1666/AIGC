# AIGC Cognitive Phase Pipeline

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

The trigger is simple:

```text
AIGC
```

The behavior behind it must be structured.

AIGC treats the trigger as the entrance to a governed, interleaved pipeline:

```text
AIGC narration
  -> Phase 1 cognitive phase router
  -> project profile and run-mode selection
  -> phase plan across slots 1-26
  -> Phase 2-24 cognitive continuity bridge
  -> phase interleave scheduler
  -> auto-approval gate procurement
  -> MVP+++ capability ledger
  -> Phase 25 repository constellation map
  -> Phase 26 refactor plan
  -> employer deliverable procurement packet
  -> submission approval cockpit
  -> uploaded workflow artifact bundle
```

The router decides what is necessary. The continuity bridge makes phases 2-24 visible. The interleave scheduler shows which phases must recur between other phases. The auto-approval gate layer classifies what can auto-pass, what requires review, and what must be denied. The terminal output is not a raw phase-map publication; it is a reviewable employer deliverable package and approval cockpit.

## Pipeline Stages

| Stage | Function |
|---|---|
| Trigger Intake | Accepts `AIGC` from manual workflow dispatch or issue/PR comment. |
| Phase 1 Cognitive Router | Reads the narration, detects intent, selects profile, and emits a phase plan. |
| Phase 2-24 Continuity Bridge | Reviews phases 2 through 24, classifies readiness, dependency state, approval state, reserved state, and required artifacts. |
| Phase Interleave Scheduler | Expands the phase plan into repeated occurrences such as guard, audit, verification, approval, quality, observability, and evolution loops. |
| Auto-Approval Gate Procurement | Applies risk-tier gate policy: auto-pass internal artifact stages, require review for elevated authority, auto-deny forbidden actions. |
| MVP+++ Procurement | Records requested elevated capability state as procurement intent while keeping effective runtime authority governed. |
| Phase 25 | Classifies repository files into ontology, taxonomy, methodology, agent lane, risk class, and constellation zone. |
| Phase 26 | Converts the Phase 25 map into a responsible refactor proposal without moving files. |
| Employer Deliverable Procurement | Recognizes the task/job/occupational discipline, instantiates the agent constellation, applies ology research, data analytics, best/emerging practices, reasoning, and metacognition, then prepares the employer-facing packet. |
| Submission Approval Cockpit | Displays audit view and lets the operator choose review_only, proceed, or deny. |
| Artifact Upload | Uploads plans, manifests, reports, audit ledgers, employer packet, and approval cockpit decision artifacts. |

## Cognitive Parameters

The pipeline considers:

- trigger phrase;
- narration text;
- project profile;
- run mode;
- detected intents;
- phase dependency;
- repeated phase occurrences;
- guard phase placement;
- occupational discipline;
- employer deliverable readiness;
- effective runtime authority;
- auto-approval gate policy;
- whether a phase is safe to run in the workflow;
- whether a phase requires human review or an approval gate.

## Supported Run Modes

| Run mode | Meaning |
|---|---|
| `plan_only` | Produce only a cognitive phase plan. |
| `artifact_generation` | Produce the Phase 1 plan, Phase 2-24 continuity ledger, interleave schedule, auto-approval gate packet, MVP+++ packet, Phase 25 manifest, Phase 26 refactor plan, employer deliverable packet, and submission approval cockpit. |
| `safe_sweep` | Produce a tighter safety-oriented plan and the safe artifact bundle. |
| `project_pipeline` | Produce a broader project-work plan across business, governance, quality, employer deliverable, and approval stages. |

## Phase Continuum

The router knows the AIGC procedure slots from 1 to 26.

The continuity bridge fills the middle layer:

```text
phase2  -> opportunity radar visibility
phase3  -> ology assessment dependency
phase4  -> proposal drafting dependency
phase5  -> approval gate
phase6  -> controlled execution gate
phase7  -> audit packet dependency
phase8  -> evolution review gate
phase9  -> reserved verification tribunal
phase10 -> connector governance
phase11 -> security vault
phase12 -> observability
phase13 -> simulation arena
phase14 -> runtime preflight
phase15 -> finance/contracts ledger
phase16 -> compliance/legal review
phase17 -> incident response
phase18 -> productization readiness
phase19 -> sub-agent forge
phase20 -> fidelity forge
phase21 -> customer satisfaction continuum
phase22 -> quality kernel
phase23 -> work order governor
phase24 -> autonomic business pipeline
```

Some phases are currently executable by explicit scripts. Other phases are planned, reserved, review-gated, or dependent on upstream artifacts.

This is intentional:

```text
reason about all phases
record phases 2-24 in a continuity ledger
schedule repeated guard loops between phases
procure auto-approval gate decisions
prepare the employer-facing deliverable
show the audit before submission approval
execute only safe known stages
record why the rest are gated
```

## Interleaved Phase Doctrine

A phase number is the canonical capability. A phase occurrence is a specific pass through that capability.

Examples:

```text
phase14@before:phase6     -> runtime preflight before controlled execution
phase5@before:phase6      -> approval gate before controlled execution
phase9@after:phase25      -> verification after constellation mapping
phase20@after:phase26     -> fidelity review after refactor planning
phase8@after:phase6       -> evolution loop after controlled execution
```

This allows a phase such as Phase 9, Phase 14, Phase 16, Phase 20, or Phase 22 to appear multiple times between other numbered phases when the project requires it.

## Employer Deliverable Doctrine

The phase map is internal. The employer-facing output is a polished deliverable procurement packet.

The employer deliverable stage recognizes:

- task/job/occupational discipline;
- agent roles needed for that discipline;
- requirements and acceptance criteria;
- best practices and emerging practices;
- relevant ologies;
- data analytics and quality metrics;
- verification and fidelity requirements;
- value proposition for the employer.

It prepares the strongest reviewable packet possible, but it does not submit externally and it does not guarantee payment.

## Submission Approval Cockpit Doctrine

The final approval is a viewing of the audit followed by a decision:

```text
review_only -> inspect audit, keep pending
proceed     -> exact phrase required; records approval_for_submission_handoff only
deny        -> exact phrase required; blocks submission handoff
```

Proceed does not silently submit externally. It records approval for a future submission handoff, subject to whatever live connector and employer-channel policy is later approved.

## Auto-Approval Gate Doctrine

Auto-approval means automatic policy classification, not automatic permission.

```text
safe internal artifact stage -> auto_pass_internal_only
elevated authority stage -> human_review_required
forbidden action -> auto_deny
```

Auto-approval cannot approve:

- raw secret value logging;
- credential use;
- external actions;
- identity use;
- physical file moves;
- source rewrites;
- workflow rewrites;
- payment, spending, live messaging, or deletion without review.

## Safety Doctrine

The pipeline does not grant live external authority.

```text
external_action_allowed = false
physical_file_moves_allowed = false
source_rewrite_allowed = false
workflow_rewrite_allowed = false
credential_use_allowed = false
secret_value_logging_allowed = false
approval_required_for_future_write_back = true
```

Future activation of dangerous capabilities requires a separate reviewed implementation, exact approval, allowlists, rollback paths, and audit receipts.

## GitHub Actions Triggering

The workflow triggers from:

1. Manual workflow dispatch.
2. Issue or pull request comment containing `AIGC`.

The workflow is intentionally not self-triggering on push. That keeps execution explicit and avoids hidden automation loops.

## Manual Local Pipeline

The complete local order is:

```powershell
python .\src\phase1_cognitive_phase_router.py --project-root . --config config\aigc_cognitive_phase_router.json --trigger-text "AIGC" --project-profile auto --run-mode artifact_generation
python .\src\phase2_24_continuity_bridge.py --project-root . --config config\aigc_phase2_24_continuity.json
python .\src\phase_interleave_scheduler.py --project-root . --config config\aigc_phase_interleave_scheduler.json
python .\src\auto_approval_gate_procurement.py --project-root . --config config\aigc_auto_approval_gates.json
python .\src\mvp_plus_plus_plus_procurement.py --project-root . --config config\mvp_plus_plus_plus_capability_procurement.json
python .\src\phase25_constellation_fabric.py --project-root . --config config\phase25_constellation_fabric.json --trigger-text "AIGC"
python .\src\phase26_constellation_refactor.py --project-root . --config config\phase26_constellation_refactor.json
python .\src\employer_deliverable_procurement.py --project-root . --config config\aigc_employer_deliverable_procurement.json
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision review_only
```

Proceed after audit review:

```powershell
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision proceed --phrase "PROCEED AIGC SUBMISSION"
```

Deny after audit review:

```powershell
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision deny --phrase "DENY AIGC SUBMISSION"
```

## Artifact Bundle

The complete workflow artifact bundle is:

```text
aigc-pipeline-artifacts
```

Expected contents include the internal phase artifacts, employer deliverable procurement packet, and submission approval cockpit:

- `data/phase1_cognitive_router/aigc_phase1_cognitive_plan.json`
- `data/phase2_24_continuity/aigc_phase2_24_continuity_plan.json`
- `data/phase_interleaves/aigc_phase_interleave_schedule.json`
- `data/auto_approval_gates/aigc_auto_approval_gate_packet.json`
- `data/mvp_plus_plus_plus/aigc_mvp_plus_plus_plus_procurement_packet.json`
- `data/phase25_constellation/aigc_phase25_constellation_manifest.json`
- `data/phase26_constellation_refactor/aigc_phase26_refactor_plan.json`
- `data/employer_deliverables/aigc_employer_deliverable_procurement_packet.json`
- `data/submission_approval/aigc_submission_approval_decision.json`
- `reports/employer_deliverable_procurement_report.md`
- `reports/submission_approval_cockpit.md`

## Short Form

```text
AIGC is the word.
Phase 1 is the mind.
Phases 2-24 are the middle spine.
Interleaves are the recurring guardians.
Auto-approval gates are the law of passage.
MVP+++ is the capability ledger.
Phase 25 is the map.
Phase 26 is the migration chart.
Employer procurement prepares the payable work.
The approval cockpit decides whether it leaves the forge.
```
