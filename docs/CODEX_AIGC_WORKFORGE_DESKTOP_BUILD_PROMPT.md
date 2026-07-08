# Codex Build Prompt: AIGC WorkForge Desktop

Use this prompt inside Codex to build the desktop application scaffold.

## Objective

Build `AIGC WorkForge Desktop`, a simple local-first desktop application for Windows laptop use.

The app must provide tabs for:

1. Dashboard
2. Work Sources
3. Secret Manager
4. Pipeline
5. Employer Packet
6. Audit & Approval
7. Settings

## Core Contract

The app must never store or display raw secrets.

It should read and generate only AIGC artifacts, reports, and secret references.

The app must support this pipeline:

```text
AIGC trigger
  -> Secret Manager reference plan
  -> work-source gate catalog
  -> access automation procurement
  -> connector allowlist requirement
  -> no raw secret logging
  -> audit receipts
  -> employer packet
  -> submission cockpit
  -> proceed/deny decision
```

## Secret Reference Procurement Contract

Read and implement:

```text
docs/AIGC_GOOGLE_SECRET_REFERENCE_PROCUREMENT_MATRIX.md
```

The app must support these Google Secret Manager references:

```text
gcp_secret://AIGC_OPERATOR_GOOGLE_WORKSPACE_EMAIL/latest
gcp_secret://AIGC_GMAIL_OAUTH_CLIENT_ID/latest
gcp_secret://AIGC_GMAIL_OAUTH_CLIENT_SECRET/latest
gcp_secret://AIGC_GMAIL_REFRESH_TOKEN/latest
```

For each reference, the app must show:

```text
reference URI
presence status
version/alias status
classification
purpose
required-before stage
rotation policy
last audit receipt
redaction status
missing-reference warning
```

The app must never show:

```text
raw OAuth client material
raw refresh credential material
raw credential values
raw token values
raw secret payloads
```

The Secret Manager tab must include:

- Generate command plan.
- Copy gcloud commands without values.
- Validate reference presence without printing values.
- Mark missing references.
- Block Proceed when required references are missing.
- Show rotation due status.
- Show last audit receipt.

## Recommended Stack

```text
Electron + React + TypeScript frontend
Python FastAPI backend
SQLite local metadata store
Python subprocess runner for existing AIGC scripts
GitHub CLI integration for workflow dispatch and artifact download
gcloud command-plan generation for Secret Manager setup
```

## Create These Paths

```text
apps/aigc-workforge-desktop/
  package.json
  electron/main.ts
  electron/preload.ts
  src/App.tsx
  src/tabs/Dashboard.tsx
  src/tabs/WorkSources.tsx
  src/tabs/SecretManager.tsx
  src/tabs/Pipeline.tsx
  src/tabs/EmployerPacket.tsx
  src/tabs/ApprovalCockpit.tsx
  src/tabs/Settings.tsx
  src/api/client.ts
  src/types/aigc.ts
  backend/main.py
  backend/routes/health.py
  backend/routes/pipeline.py
  backend/routes/sources.py
  backend/routes/secrets.py
  backend/routes/employer.py
  backend/routes/approval.py
  backend/services/pipeline_runner.py
  backend/services/artifact_reader.py
  backend/services/secret_reference_checker.py
  backend/services/github_cli.py
  backend/services/gcloud_plan.py
  backend/storage/db.py
```

## UI Requirements

- Keep the UI simple and tabbed.
- Use large clear buttons.
- Use status cards.
- Use tables for source gates.
- Use a read-only audit viewer.
- Use proceed and deny buttons with exact phrase confirmation.
- Show warnings when the user tries to proceed without required artifacts.
- Do not show raw secrets.

## Backend Requirements

Implement endpoints:

```text
GET  /health
GET  /settings
POST /settings
POST /pipeline/local-run
POST /pipeline/github-dispatch
GET  /pipeline/latest-run
POST /pipeline/download-artifact
GET  /sources/gates
GET  /secrets/references
GET  /secrets/procurement-matrix
POST /secrets/command-plan
POST /secrets/validate-references
GET  /employer/latest-packet
GET  /audit/latest
POST /submission/review-only
POST /submission/proceed
POST /submission/deny
```

## Pipeline Commands

Local pipeline:

```powershell
python .\src\phase1_cognitive_phase_router.py --project-root . --config config\aigc_cognitive_phase_router.json --trigger-text "AIGC" --project-profile auto --run-mode artifact_generation
python .\src\phase2_24_continuity_bridge.py --project-root . --config config\aigc_phase2_24_continuity.json
python .\src\phase_interleave_scheduler.py --project-root . --config config\aigc_phase_interleave_scheduler.json
python .\src\google_workspace_secret_manager_procurement.py --project-root . --config config\aigc_google_workspace_secret_manager_procurement.json
python .\src\mvp_plus_plus_plus_procurement.py --project-root . --config config\mvp_plus_plus_plus_capability_procurement.json
python .\src\access_automation_procurement.py --project-root . --config config\aigc_access_automation_procurement.json
python .\src\work_source_gate_procurement.py --project-root . --config config\aigc_work_source_gate_catalog.json
python .\src\auto_approval_gate_procurement.py --project-root . --config config\aigc_auto_approval_gates.json
python .\src\phase25_constellation_fabric.py --project-root . --config config\phase25_constellation_fabric.json --trigger-text "AIGC"
python .\src\phase26_constellation_refactor.py --project-root . --config config\phase26_constellation_refactor.json
python .\src\employer_deliverable_procurement.py --project-root . --config config\aigc_employer_deliverable_procurement.json
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision review_only
```

GitHub Actions dispatch:

```powershell
gh workflow run aigc_constellation_trigger.yml -f narration="AIGC" -f project_profile="auto" -f run_mode="artifact_generation" -f submission_decision="review_only"
```

## Approval Rules

Proceed requires exact phrase:

```text
PROCEED AIGC SUBMISSION
```

Deny requires exact phrase:

```text
DENY AIGC SUBMISSION
```

Proceed records handoff authority only. It does not silently submit externally.

## Safety Invariants

- No raw secrets in UI.
- No raw secrets in logs.
- No raw secrets in repo.
- No raw secrets in artifacts.
- Submission requires cockpit approval.
- External connector activation requires separate future review.
- Source terms and API/robots policy checks must be shown per source.
- Work-source gates must be visible before any connector is marked active.
- Secret references must be validated by presence/status only.
- Missing required secret references block Proceed.

## Deliverable

Build a runnable scaffold that can load existing AIGC artifacts and run the local pipeline. Focus on clarity, safety, and investor-demo polish before complex live integrations.
