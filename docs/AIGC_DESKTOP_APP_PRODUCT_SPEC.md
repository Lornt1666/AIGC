# AIGC Desktop Application Product Spec

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Product Name

**AIGC WorkForge Desktop**

## Prime Thesis

AIGC WorkForge Desktop is a simple, local-first laptop application that lets the operator run the AIGC work-procurement pipeline without touching raw secrets, terminal complexity, or hidden automation.

```text
AIGC trigger
  -> source/domain controls
  -> Google Secret Manager references
  -> access automation procurement
  -> employer deliverable packet
  -> audit review
  -> proceed / deny
```

The app is not a spam tool. It is a governed work-procurement cockpit for finding legitimate work, preparing high-quality submissions, and requiring human review before anything leaves the forge.

## Investable Product Position

AIGC WorkForge Desktop is positioned as:

> A governed AI work-procurement operating system for freelancers, builders, researchers, agencies, and technical operators.

Core value:

- Converts work opportunities into structured deliverable packets.
- Coordinates agent roles, research, analytics, ologies, and quality checks.
- Keeps secrets in Google Secret Manager.
- Generates full audit trails.
- Requires explicit human approval before submission.
- Supports source-domain discipline across job boards, marketplaces, RFP portals, GitHub issues, and direct career pages.

## Target User

Primary user:

- Independent operator seeking paid work, tasks, jobs, contracts, RFPs, bounties, or client opportunities.

Secondary users:

- Small agencies.
- Technical freelancers.
- Builders/trades operators.
- Researchers and consultants.
- AI-assisted business operators.

## Desktop Stack Recommendation

Recommended Codex build target:

```text
Frontend: React + TypeScript
Desktop shell: Tauri or Electron
Local API: Python FastAPI
Local storage: SQLite
Pipeline runner: Python subprocess wrapper
Secrets: Google Secret Manager references only
Workflow bridge: GitHub CLI / GitHub Actions dispatch
```

Default MVP choice:

```text
Electron + React + TypeScript + FastAPI + SQLite
```

Reason: fastest Codex implementation path, mature desktop packaging, easy file handling, simple local API, and straightforward integration with the existing Python scripts.

## Application Tabs

### 1. Dashboard

Purpose:

- Show pipeline status.
- Show last run ID.
- Show latest artifact bundle.
- Show readiness score.
- Show current decision state.

Widgets:

- Run AIGC Pipeline button.
- Review Latest Audit button.
- Proceed / Deny status indicator.
- Secret Manager health indicator.
- Source gate summary.

### 2. Work Sources

Purpose:

- Display all source domains and gate status.

Rows:

- RemoteOK
- Remotive
- WeWorkRemotely
- Wellfound
- FlexJobs
- Indeed
- LinkedIn Jobs
- Glassdoor
- ZipRecruiter
- Upwork
- Freelancer
- Guru
- PeoplePerHour
- Contra
- Toptal
- GitHub Issues
- GitLab Issues
- IssueHunt
- CanadaBuys
- MERX
- Alberta Purchasing Connection
- SAM.gov
- Kijiji
- Craigslist
- Facebook Groups
- local classifieds
- Greenhouse
- Lever
- Workday
- Ashby
- SmartRecruiters

Each row shows:

- source terms review;
- access mode;
- robots/API check;
- connector allowlist status;
- secret-reference status;
- rate-limit policy;
- redaction status;
- audit status;
- manual handoff path.

### 3. Secret Manager

Purpose:

- Show secret references and whether each expected secret exists.
- Never display raw secret values.

Displays:

- `AIGC_OPERATOR_GOOGLE_WORKSPACE_EMAIL`
- `AIGC_GCP_PROJECT_ID`
- `AIGC_GMAIL_OAUTH_CLIENT_ID`
- `AIGC_GMAIL_OAUTH_CLIENT_SECRET`
- `AIGC_GMAIL_REFRESH_TOKEN`
- `AIGC_WORK_SOURCE_CONNECTOR_ALLOWLIST`

Buttons:

- Generate Google Secret Manager Command Plan.
- Copy gcloud Create Commands.
- Mark Secret Configured.
- Run Local Secret Reference Audit.

Never allowed:

- paste raw secret into repo;
- write raw secret into logs;
- display raw refresh token;
- export raw secrets into artifacts.

### 4. Pipeline

Purpose:

- Run the AIGC pipeline locally or dispatch GitHub Actions.

Inputs:

- narration: default `AIGC`
- project profile: `auto`, `constellation_refactor`, `business_pipeline`, `security_governance`, `full_continuum`
- run mode: `plan_only`, `artifact_generation`, `safe_sweep`, `project_pipeline`
- submission decision: `review_only`, `proceed`, `deny`
- submission phrase: optional exact phrase

Buttons:

- Run Local Pipeline.
- Dispatch GitHub Workflow.
- Fetch Latest Run.
- Download Artifact Bundle.
- Open Artifact Folder.

### 5. Employer Packet

Purpose:

- Show the generated employer-facing deliverable procurement packet.

Sections:

- occupational discipline recognition;
- agent constellation;
- requirements and acceptance criteria;
- best practices and emerging practices;
- ology research synthesis;
- data analytics and quality metrics;
- solution or work product plan;
- verification and fidelity review;
- value proposition for employer;
- risk limitations.

### 6. Audit & Approval Cockpit

Purpose:

- Final human-in-loop review.

Displays:

- audit summary;
- source gates;
- secret reference health;
- employer packet readiness;
- redaction results;
- submission readiness score.

Buttons:

- Review Only.
- Proceed.
- Deny.

Proceed requires exact phrase:

```text
PROCEED AIGC SUBMISSION
```

Deny requires exact phrase:

```text
DENY AIGC SUBMISSION
```

Proceed behavior:

- records approval for submission handoff;
- does not silently send unless a future approved live connector exists;
- writes an audit decision artifact.

### 7. Settings

Purpose:

- Configure local paths and tool availability.

Settings:

- repo path;
- Python path;
- GitHub CLI path;
- gcloud path;
- artifact download folder;
- Google Cloud project reference;
- default pipeline mode;
- enable/disable source categories;
- strict review mode.

## Local Backend API

Recommended FastAPI endpoints:

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
POST /secrets/command-plan
GET  /employer/latest-packet
GET  /audit/latest
POST /submission/review-only
POST /submission/proceed
POST /submission/deny
```

## Local Data Model

SQLite tables:

```text
settings
pipeline_runs
artifact_bundles
source_gates
secret_references
employer_packets
submission_decisions
audit_events
```

## Security Invariants

- Raw secrets never enter app logs.
- Raw secrets never enter the repo.
- Raw secrets never enter GitHub Actions artifacts.
- Gmail send scope is the narrow default.
- Broader Gmail scopes require separate review.
- Source connector activation requires allowlist.
- External submission requires cockpit proceed.
- Proceed records handoff authority only unless a future live connector is separately approved.
- Deny blocks handoff.

## MVP Screens

Minimum investable MVP:

1. Dashboard
2. Work Sources
3. Secret Manager
4. Pipeline
5. Employer Packet
6. Audit & Approval
7. Settings

## Milestone Plan

### Milestone 1: Local UI Shell

- Build desktop shell.
- Add tabs.
- Read repo path.
- Show static source gate catalog.

### Milestone 2: Pipeline Runner

- Run local Python pipeline commands.
- Show stdout/stderr.
- Load generated JSON and reports.

### Milestone 3: Secret Manager Control Plane

- Render secret references.
- Generate gcloud command plan.
- Confirm reference-only status.

### Milestone 4: GitHub Actions Bridge

- Dispatch workflow through `gh workflow run`.
- Poll latest run.
- Download artifact bundle.

### Milestone 5: Employer Packet UI

- Display employer deliverable packet.
- Show discipline, agents, ologies, data analytics, and readiness.

### Milestone 6: Submission Approval Cockpit

- Render audit.
- Add proceed/deny buttons.
- Require exact phrase.
- Record decision artifact.

### Milestone 7: Packaging

- Package for Windows laptop.
- Add signed installer later.
- Add investor demo mode with synthetic data.

## Codex Build Instruction

Build the app in `apps/aigc-workforge-desktop/`.

Use a clean modular architecture:

```text
apps/aigc-workforge-desktop/
  package.json
  electron/
    main.ts
    preload.ts
  src/
    App.tsx
    tabs/
      Dashboard.tsx
      WorkSources.tsx
      SecretManager.tsx
      Pipeline.tsx
      EmployerPacket.tsx
      ApprovalCockpit.tsx
      Settings.tsx
    api/
      client.ts
    types/
      aigc.ts
  backend/
    main.py
    routes/
      health.py
      pipeline.py
      sources.py
      secrets.py
      employer.py
      approval.py
    services/
      pipeline_runner.py
      artifact_reader.py
      secret_reference_checker.py
      github_cli.py
      gcloud_plan.py
    storage/
      db.py
```

## Short Form

```text
One button starts the forge.
Tabs show the work.
Secrets stay in Google.
Sources pass gates.
The employer packet is reviewed.
Proceed or deny decides what leaves.
```
