# AIGC Cognitive Phase Pipeline

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

The trigger is simple:

```text
AIGC
```

The behavior behind it must be structured.

AIGC treats the trigger as the entrance to a governed pipeline:

```text
AIGC narration
  -> Phase 1 cognitive phase router
  -> project profile and run-mode selection
  -> phase plan across slots 1-26
  -> Phase 2-24 cognitive continuity bridge
  -> explicit safe artifact stages
  -> uploaded workflow artifact bundle
```

The router decides what is necessary. The continuity bridge makes phases 2-24 visible. The workflow executes only known safe artifact stages.

## Pipeline Stages

| Stage | Function |
|---|---|
| Trigger Intake | Accepts `AIGC` from manual workflow dispatch or issue/PR comment. |
| Phase 1 Cognitive Router | Reads the narration, detects intent, selects profile, and emits a phase plan. |
| Phase 2-24 Continuity Bridge | Reviews phases 2 through 24, classifies readiness, dependency state, approval state, reserved state, and required artifacts. |
| MVP+++ Procurement | Records requested elevated capability state as procurement intent while keeping effective runtime authority governed. |
| Phase 25 | Classifies repository files into ontology, taxonomy, methodology, agent lane, risk class, and constellation zone. |
| Phase 26 | Converts the Phase 25 map into a responsible refactor proposal without moving files. |
| Artifact Upload | Uploads plans, manifests, reports, and audit ledgers as workflow artifacts. |

## Cognitive Parameters

The pipeline considers:

- trigger phrase;
- narration text;
- project profile;
- run mode;
- detected intents;
- phase dependency;
- effective runtime authority;
- whether a phase is safe to run in the workflow;
- whether a phase requires human review or an approval gate.

## Supported Run Modes

| Run mode | Meaning |
|---|---|
| `plan_only` | Produce only a cognitive phase plan. |
| `artifact_generation` | Produce the Phase 1 plan, Phase 2-24 continuity ledger, MVP+++ packet, Phase 25 manifest, and Phase 26 refactor plan. |
| `safe_sweep` | Produce a tighter safety-oriented plan and the safe artifact bundle. |
| `project_pipeline` | Produce a broader project-work plan across business, governance, quality, and constellation phases. |

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
execute only safe known stages
record why the rest are gated
```

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

Until the workflow includes the Phase 2-24 continuity step directly, run the complete local order as:

```powershell
python .\src\phase1_cognitive_phase_router.py --project-root . --config config\aigc_cognitive_phase_router.json --trigger-text "AIGC" --project-profile auto --run-mode artifact_generation
python .\src\phase2_24_continuity_bridge.py --project-root . --config config\aigc_phase2_24_continuity.json
python .\src\mvp_plus_plus_plus_procurement.py --project-root . --config config\mvp_plus_plus_plus_capability_procurement.json
python .\src\phase25_constellation_fabric.py --project-root . --config config\phase25_constellation_fabric.json --trigger-text "AIGC"
python .\src\phase26_constellation_refactor.py --project-root . --config config\phase26_constellation_refactor.json
```

## Artifact Bundle

The intended complete artifact bundle is:

```text
aigc-mvp-plus-plus-plus-phase1-phase2-24-phase25-phase26-constellation-fabric
```

Expected contents:

- `data/phase1_cognitive_router/aigc_phase1_cognitive_plan.json`
- `data/phase2_24_continuity/aigc_phase2_24_continuity_plan.json`
- `data/mvp_plus_plus_plus/aigc_mvp_plus_plus_plus_procurement_packet.json`
- `data/phase25_constellation/aigc_phase25_constellation_manifest.json`
- `data/phase26_constellation_refactor/aigc_phase26_refactor_plan.json`
- `data/audit/aigc_phase1_cognitive_router_audit.jsonl`
- `data/audit/aigc_phase2_24_continuity_audit.jsonl`
- `data/audit/aigc_mvp_plus_plus_plus_procurement_audit.jsonl`
- `data/audit/aigc_phase25_audit.jsonl`
- `data/audit/aigc_phase26_audit.jsonl`
- `reports/phase1_cognitive_router_report.md`
- `reports/phase2_24_continuity_report.md`
- `reports/mvp_plus_plus_plus_procurement_report.md`
- `reports/phase25_constellation_fabric_report.md`
- `reports/phase26_constellation_refactor_report.md`

## Short Form

```text
AIGC is the word.
Phase 1 is the mind.
Phases 2-24 are the middle spine.
MVP+++ is the capability ledger.
Phase 25 is the map.
Phase 26 is the migration chart.
The workflow is the pipe.
```
