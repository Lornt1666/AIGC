# AIGC Google Workspace Secret Manager Procurement

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

AIGC can coordinate with Google Workspace and Gmail only through a reference-only secret control plane.

```text
Google Workspace identity
  -> Google Secret Manager references
  -> Gmail OAuth scope minimization
  -> connector allowlist
  -> no raw secrets in repo or logs
  -> audit receipt
  -> submission cockpit before employer contact
```

## Secret Storage Rule

The repository stores only references such as:

```text
gcp_secret://AIGC_GMAIL_OAUTH_CLIENT_ID/latest
gcp_secret://AIGC_GMAIL_OAUTH_CLIENT_SECRET/latest
gcp_secret://AIGC_GMAIL_REFRESH_TOKEN/latest
```

It must not store raw client secrets, refresh tokens, API keys, passwords, certificates, or private keys.

## Planned Secrets

- `AIGC_OPERATOR_GOOGLE_WORKSPACE_EMAIL`
- `AIGC_GCP_PROJECT_ID`
- `AIGC_GMAIL_OAUTH_CLIENT_ID`
- `AIGC_GMAIL_OAUTH_CLIENT_SECRET`
- `AIGC_GMAIL_REFRESH_TOKEN`
- `AIGC_WORK_SOURCE_CONNECTOR_ALLOWLIST`

## Gmail Scope Doctrine

Start with the narrowest useful scope, such as Gmail send, and escalate only after review. Broader compose, modify, or full-mail scopes require separate review.

## Command Plan

The generated procurement packet includes `gcloud` commands as a plan only. This stage does not mutate Google Cloud.

## Local Run

```powershell
python .\src\google_workspace_secret_manager_procurement.py --project-root . --config config\aigc_google_workspace_secret_manager_procurement.json
```

## Outputs

- `data/google_workspace_secret_manager/aigc_google_workspace_secret_manager_procurement_packet.json`
- `reports/google_workspace_secret_manager_procurement_report.md`
- `data/audit/aigc_google_workspace_secret_manager_procurement_audit.jsonl`

## Safety Boundary

No Google Cloud mutation, credential use, raw secret logging, or external employer submission occurs in this stage.

## Short Form

```text
Secrets live in Google.
AIGC stores references.
The cockpit decides what leaves.
```
