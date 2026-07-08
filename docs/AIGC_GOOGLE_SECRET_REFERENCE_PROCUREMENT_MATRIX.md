# AIGC Google Secret Reference Procurement Matrix

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

These Google references are human-in-loop capability procurement objects. They are not raw credentials inside AIGC.

```text
AIGC trigger
  -> Google Secret Manager reference check
  -> Gmail scope discipline
  -> source gates
  -> audit receipt
  -> employer packet
  -> submission cockpit
  -> proceed or deny
```

Raw values must be entered only inside Google Secret Manager by the operator. AIGC stores only reference strings, status, version metadata, validation status, and audit receipts.

## Required References

| Reference | Purpose | Required before | Display rule |
|---|---|---|---|
| `gcp_secret://AIGC_OPERATOR_GOOGLE_WORKSPACE_EMAIL/latest` | Operator Google Workspace identity for audit, ownership, and Gmail handoff context. | OAuth consent and submission cockpit identity display. | Masked identity only unless local operator chooses full display. |
| `gcp_secret://AIGC_GMAIL_OAUTH_CLIENT_ID/latest` | OAuth client identifier for the approved Gmail connector. | OAuth authorization URL generation and Gmail connector dry-run. | Reference and status only. |
| `gcp_secret://AIGC_GMAIL_OAUTH_CLIENT_SECRET/latest` | OAuth client credential material for token exchange when required by the approved app type. | Token exchange, if required. | Never display raw value. |
| `gcp_secret://AIGC_GMAIL_REFRESH_TOKEN/latest` | Refresh credential generated only after operator grants offline access in the Google OAuth flow. | Approved Gmail connector after submission cockpit proceed. | Never display raw value. |

## Procurement Requirements Per Reference

Each reference must carry:

```text
secret_id
reference_uri
classification
purpose
expected_shape
source_of_truth
required_before
least_privilege_access
rotation_policy
redaction_policy
audit_events
forbidden_outputs
```

## Google Secret Manager Rules

- Secret Manager stores the raw values.
- AIGC stores only `gcp_secret://...` references.
- Secret versions, access status, and audit events may be recorded.
- Raw values must not enter the repo, app UI, logs, GitHub Actions, artifacts, reports, ChatGPT messages, or Codex prompts.
- IAM must follow least privilege.
- Secret-level access is preferred where possible.
- Rotation and revocation procedures must be documented.

## Gmail OAuth Rules

- Start with the narrowest useful Gmail scope.
- `gmail.send` is the initial send-only scope.
- Broader compose, modify, or full-mail scopes require separate review.
- Offline access is required if the operator wants a refresh credential for approved unattended token refresh.
- The OAuth state parameter must be used to protect the authorization flow.
- Submission still requires the AIGC Submission Approval Cockpit.

## Desktop App Requirements

AIGC WorkForge Desktop must:

- show reference status;
- show secret version status;
- show whether a required reference is missing;
- show rotation due status;
- show last audit receipt;
- generate gcloud command plans without values;
- block proceed if required references are missing;
- never display raw credential values.

## Proceed Boundary

Proceed requires:

```text
PROCEED AIGC SUBMISSION
```

Proceed records handoff authority only. Nothing silently submits.

## Short Form

```text
Secrets live in Google.
AIGC sees references.
The desktop sees status.
The cockpit decides what leaves.
```
