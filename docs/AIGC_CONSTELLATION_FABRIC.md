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

The result is not hidden autonomy. It is visible autonomy: every file receives a place in the constellation before any future refactor is proposed.

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
classify -> report -> review -> approve -> refactor in a separate PR
```

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
| Audit Archivist | Writes the manifest, report, and audit entry. |
| Constellation Cartographer | Produces the final map and next-action directives. |

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
  -> artifact report
```

No tokens, credentials, or raw private chat logs belong in the repository.

## Local Run

```powershell
python .\src\phase25_constellation_fabric.py --project-root . --config config\phase25_constellation_fabric.json --force-local
```

Outputs:

- `data/phase25_constellation/aigc_phase25_constellation_manifest.json`
- `reports/phase25_constellation_fabric_report.md`
- `data/audit/aigc_phase25_audit.jsonl`

## Cloud Run

Manual cloud trigger:

```powershell
gh workflow run aigc_constellation_trigger.yml -f narration="AIGC: run constellation fabric classification."
```

GitHub issue or PR comment trigger:

```text
AIGC: run constellation fabric classification.
```

The workflow uploads the manifest, report, and audit ledger as GitHub Actions artifacts. It does not commit generated output back into the repo.

## Operational Safety Doctrine

Phase 25 obeys these boundaries:

```text
external_action_allowed = false
physical_file_moves_allowed = false
credential_use_allowed = false
secret_value_logging_allowed = false
cloud_write_back_allowed = false
approval_required_for_future_write_back = true
```

This means the constellation can see the board, name the pieces, and draw the map. It cannot secretly move the pieces.

## Future Physical Refactor Plan

After reviewing the Phase 25 manifest, a future PR can add a controlled refactor mode that generates move proposals such as:

```text
source path -> constellation zone path -> reason -> risk -> approval state
```

That future refactor should remain human-reviewed and should preserve imports, tests, workflows, documentation links, and audit history.

## Short Form

AIGC Phase 25 is the bridge between the myth and the machine:

```text
word -> trigger
trigger -> arena
arena -> ontology
ontology -> file map
file map -> agent lanes
agent lanes -> governed work
```

The constellation wakes when AIGC is spoken, but it moves only under law.
