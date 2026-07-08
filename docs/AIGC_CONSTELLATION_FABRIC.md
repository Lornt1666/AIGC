# AIGC Constellation Fabric

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

AIGC is the Digital Worker constellation: a governed fabric of specialized agents that sort, classify, reason, draft, verify, audit, and prepare work while keeping external action behind explicit approval gates.

Phase 25 adds the **Constellation Fabric** layer. Its job is to map the repository itself into an operational formality:

```text
narrate AIGC
  -> detect approved trigger signal
  -> classify repository files
  -> map each file into ontology, taxonomy, methodology, agent lane, risk class
  -> generate constellation manifest
  -> generate human-readable report
  -> write audit ledger
  -> stop before physical moves or external actions
```

Phase 26 adds the **Constellation Refactor Planner** layer. Its job is to convert the Phase 25 map into a human-reviewed migration proposal:

```text
Phase 25 manifest
  -> proposed constellation target paths
  -> dependency and workflow risk flags
  -> retained-in-place decisions
  -> move-candidate ledger
  -> human-reviewed future PR boundary
```

The result is not hidden autonomy. It is visible autonomy: every file receives a place in the constellation before any future physical refactor is proposed.

## What Phase 25 Does

Phase 25 performs safe repository cartography:

| Dimension | Meaning |
|---|---|
| Ontology | What kind of thing the file is. |
| Taxonomy | What class or family the file belongs to. |
| Methodology | What process or phase the file supports. |
| Agent lane | Which specialized agent should own or inspect it. |
| Risk class | Whether the artifact is doctrine, config, security-adjacent, generated data, or cloud-control metadata. |
| Constellation zone | The operational folder domain where the artifact belongs conceptually. |

Phase 25 does **not** move files by default. The correct sequence is:

```text
classify -> report -> review -> plan refactor -> review again -> refactor in a separate PR
```

## What Phase 26 Does

Phase 26 reads the Phase 25 manifest and writes a proposal-only refactor plan. It decides whether each file is:

| Proposed action | Meaning |
|---|---|
| `move_candidate_after_review` | Could be moved in a future reviewed PR if imports, links, and tests are handled. |
| `blocked_until_dependency_review` | Must not move yet because import, workflow, docs, secret-boundary, or classification risks exist. |
| `retain_in_place_with_constellation_metadata` | Should stay where it is while still receiving constellation metadata. |

Phase 26 does **not** move files, rewrite imports, edit workflows, commit generated outputs, use credentials, or bypass approval gates.

## Constellation Zones

| Zone | Role |
|---|---|
| `00_COMMAND_DOCTRINE` | Root identity, README, license, prime operator doctrine. |
| `01_CLOUD_TRIGGER_INGRESS` | GitHub Actions, workflow dispatch, issue comments, approved chat-log bridge ingress. |
| `02_CONFIGURATION_CONTROL` | Configs, phase manifests, connector boundaries, source policy. |
| `03_CONTRACT_SCHEMA_ONTOLOGY` | Schemas and artifact contracts. |
| `04_AGENTIC_SOURCE_KERNEL` | Python source, phase engines, orchestrators, runtime core. |
| `05_SECURITY_GOVERNANCE` | Security, approvals, incident response, secret references, compliance. |
| `06_DATA_MEMORY_LEDGER` | Generated data, audit ledgers, state, memory artifacts. |
| `07_REPORTING_OBSERVABILITY` | Reports, dashboards, telemetry, health records. |
| `08_DOCS_OLOGY_LIBRARY` | Ontology, methodology, taxonomy, governance doctrine, research synthesis. |
| `09_TEST_AND_VALIDATION` | Tests, simulations, fixtures, verification gates. |
| `99_UNCLASSIFIED_SUPPORT` | Anything that needs human review before placement. |

## Agent Constellation

| Agent | Function |
|---|---|
| Arena Master | Opens the safe run after the AIGC trigger is detected. |
| Ontology Sorter | Maps each file to entity type, relation, phase, and zone. |
| Taxonomy Librarian | Groups files by domain class, artifact class, and risk class. |
| Methodology Engineer | Assigns each artifact to the process it supports. |
| Cloud Trigger Sentinel | Keeps cloud execution dry-run and artifact-only. |
| Security Governor | Marks sensitive paths and secret-adjacent files without exposing secrets. |
| Audit Archivist | Writes the manifest, report, audit entry, and refactor plan ledger. |
| Constellation Cartographer | Produces the final map and next-action directives. |
| Dependency Sentinel | Flags imports, workflow paths, documentation links, generated-artifact lineage, and secret-boundary risks before movement. |

## Trigger Model

The trigger phrase is:

```text
AIGC
```

Approved ingress surfaces:

1. Local CLI with `--force-local`.
2. GitHub Actions `workflow_dispatch` narration input.
3. GitHub issue or pull request comments containing `AIGC`.
4. A future approved chat-log bridge that sends narration text to GitHub Actions.

Important boundary:

> AIGC cannot automatically read every AI chat log everywhere unless that chat system explicitly exports or forwards the narration into this repository's approved trigger surface.

The safe bridge design is:

```text
AI chat/log source
  -> explicit user-approved export or webhook
  -> secret stored outside repo
  -> GitHub workflow_dispatch call
  -> Phase 25 dry-run classification
  -> Phase 26 dry-run refactor plan
  -> artifact report
```

No tokens, credentials, or raw private chat logs belong in the repository.

## Local Run

Unified CLI:

```powershell
python .\src\aigc.py run phase25
python .\src\aigc.py run phase26
```

Direct scripts:

```powershell
python .\src\phase25_constellation_fabric.py --project-root . --config config\phase25_constellation_fabric.json --force-local
python .\src\phase26_constellation_refactor.py --project-root . --config config\phase26_constellation_refactor.json
```

Outputs:

- `data/phase25_constellation/aigc_phase25_constellation_manifest.json`
- `reports/phase25_constellation_fabric_report.md`
- `data/audit/aigc_phase25_audit.jsonl`
- `data/phase26_constellation_refactor/aigc_phase26_refactor_plan.json`
- `reports/phase26_constellation_refactor_report.md`
- `data/audit/aigc_phase26_audit.jsonl`

## Cloud Run

Manual cloud trigger:

```powershell
gh workflow run aigc_constellation_trigger.yml -f narration="AIGC: run constellation fabric classification."
```

GitHub issue or PR comment trigger:

```text
AIGC: run constellation fabric classification.
```

The workflow uploads the Phase 25 manifest, Phase 26 refactor plan, reports, and audit ledgers as GitHub Actions artifacts. It does not commit generated output back into the repo.

## Operational Safety Doctrine

Phase 25 and Phase 26 obey these boundaries:

```text
external_action_allowed = false
physical_file_moves_allowed = false
source_rewrite_allowed = false
workflow_rewrite_allowed = false
credential_use_allowed = false
secret_value_logging_allowed = false
cloud_write_back_allowed = false
approval_required_for_future_write_back = true
```

This means the constellation can see the board, name the pieces, and draw the migration chart. It cannot secretly move the pieces.

## Future Physical Refactor Plan

After reviewing the Phase 26 plan, a future PR can perform actual moves only if it includes:

```text
source path -> target path -> reason -> risk -> import update -> docs update -> test result -> approval state
```

That future refactor must preserve imports, tests, workflows, documentation links, generated-artifact lineage, schema references, and audit history.

## Short Form

AIGC Phase 25 and Phase 26 are the bridge between the myth and the machine:

```text
word -> trigger
trigger -> arena
arena -> ontology
ontology -> file map
file map -> migration plan
migration plan -> reviewed PR
reviewed PR -> governed work
```

The constellation wakes when AIGC is spoken, but it moves only under law.
