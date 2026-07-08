# AIGC Cognitive Phase Pipeline

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

The trigger is simple:

```text
AIGC
```

The behavior behind it must be structured.

AIGC now treats the trigger as the entrance to a governed pipeline:

```text
AIGC narration
  -> Phase 1 cognitive phase router
  -> project profile and run-mode selection
  -> phase plan across slots 1-26
  -> explicit safe artifact stages
  -> uploaded workflow artifact bundle
```

The router decides what is necessary. The workflow executes only known safe artifact stages.

## Pipeline Stages

| Stage | Function |
|---|---|
| Trigger Intake | Accepts `AIGC` from workflow dispatch, issue/PR comment, or push commit message. |
| Phase 1 Cognitive Router | Reads the narration, detects intent, selects profile, and emits a phase plan. |
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
| `artifact_generation` | Produce the Phase 1 plan, MVP+++ packet, Phase 25 manifest, and Phase 26 refactor plan. |
| `safe_sweep` | Produce a tighter safety-oriented plan and the safe artifact bundle. |
| `project_pipeline` | Produce a broader project-work plan across business, governance, quality, and constellation phases. |

## Phase Continuum

The router knows the AIGC procedure slots from 1 to 26.

Some phases are currently executable by explicit workflow scripts. Other phases are planned, reserved, review-gated, or dependent on upstream artifacts.

This is intentional:

```text
reason about all phases
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
3. Push to `main` where the head commit message contains `AIGC`.

The push trigger exists so a merge commit containing `AIGC` can produce a concrete workflow run ID for inspection and artifact download.

## Artifact Bundle

The current artifact bundle is:

```text
aigc-mvp-plus-plus-plus-phase1-phase25-phase26-constellation-fabric
```

Expected contents:

- `data/phase1_cognitive_router/aigc_phase1_cognitive_plan.json`
- `data/mvp_plus_plus_plus/aigc_mvp_plus_plus_plus_procurement_packet.json`
- `data/phase25_constellation/aigc_phase25_constellation_manifest.json`
- `data/phase26_constellation_refactor/aigc_phase26_refactor_plan.json`
- `data/audit/aigc_phase1_cognitive_router_audit.jsonl`
- `data/audit/aigc_mvp_plus_plus_plus_procurement_audit.jsonl`
- `data/audit/aigc_phase25_audit.jsonl`
- `data/audit/aigc_phase26_audit.jsonl`
- `reports/phase1_cognitive_router_report.md`
- `reports/mvp_plus_plus_plus_procurement_report.md`
- `reports/phase25_constellation_fabric_report.md`
- `reports/phase26_constellation_refactor_report.md`

## Short Form

```text
AIGC is the word.
Phase 1 is the mind.
MVP+++ is the capability ledger.
Phase 25 is the map.
Phase 26 is the migration chart.
The workflow is the pipe.
```
