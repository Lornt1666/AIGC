# AIGC Credential Holder Architecture

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

AIGC WorkForge Desktop must not become its own plaintext password manager.

The application may coordinate credential saving, but the saving target must be a trusted credential vault:

```text
preferred cloud vault: Google Secret Manager
local development vault: operating-system protected storage
optional future vault: approved third-party password manager integration
```

The app stores references, status, audit receipts, and operator decisions. It does not store credential payloads in the repository, normal app database, logs, GitHub Actions, reports, or artifacts.

## Save Credential Broker

The desktop app should implement a **Save Credential Broker**.

The broker is a controlled popup that asks the operator where to save a credential:

1. Save to Google Secret Manager.
2. Save to OS-protected local storage for development only.
3. Save to an approved external password manager integration in a future reviewed connector.
4. Cancel and mark missing.

The broker must show:

- destination vault;
- reference name;
- purpose;
- required-before stage;
- scope requested;
- expiry or rotation policy;
- audit event that will be written;
- warning that the value will not be written to the repo or artifacts.

## Approved Storage Targets

### Google Secret Manager

Use for cloud/workflow-facing AIGC references.

Examples:

```text
gcp_secret://AIGC_OPERATOR_GOOGLE_WORKSPACE_EMAIL/latest
gcp_secret://AIGC_GMAIL_OAUTH_CLIENT_ID/latest
gcp_secret://AIGC_GMAIL_OAUTH_CLIENT_SECRET/latest
gcp_secret://AIGC_GMAIL_REFRESH_TOKEN/latest
```

### OS-Protected Local Storage

Use only for local desktop convenience and development when the operator explicitly chooses local storage.

Electron implementation may use OS-backed protected storage through Electron safeStorage.

Tauri implementation may use Tauri Stronghold.

Local vault entries must be marked:

```text
local_only = true
not_for_ci = true
not_for_artifacts = true
not_for_repo = true
```

## Save Flow

```text
operator clicks Save Credential
  -> app opens controlled broker popup
  -> operator chooses vault target
  -> app displays reference name and purpose
  -> operator enters value only into the vault entry surface
  -> app receives success/failure metadata only
  -> app writes audit receipt
  -> app refreshes reference status
```

## Display Rules

The app may display:

- reference URI;
- vault target;
- presence status;
- version or enabled status;
- rotation status;
- last checked time;
- last audit receipt;
- missing warning;
- scope summary;
- source of truth.

The app must not display credential payloads in ordinary UI, advanced UI, hidden UI, audit reports, logs, workflow output, or artifacts.

## Ctrl+N Advanced Panel

`Ctrl+N` may open an advanced **Credential Reference Inspector**.

It may show status and metadata only.

It must not become a plaintext credential viewer.

## No Data Loss Doctrine

To avoid losing access:

- every required credential has a named reference;
- every named reference has a setup command plan;
- every save attempt writes an audit event;
- every successful save refreshes presence status;
- rotation policy is visible;
- missing references block proceed;
- operator can export a reference inventory without payloads;
- operator can re-run the command plan at any time.

## Proceed Boundary

Proceed requires the Submission Approval Cockpit and the exact phrase:

```text
PROCEED AIGC SUBMISSION
```

Proceed records handoff authority only. Nothing silently submits.

## Short Form

```text
AIGC may coordinate saving.
The vault holds the payload.
The app holds the map.
The audit proves the path.
```
