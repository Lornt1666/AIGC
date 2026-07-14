# Production Connector and Secret Broker Baseline v1

Status: `IMPLEMENTED_INTERNAL_PENDING_STAGING_EVIDENCE`  
Parent program: issue `#83`  
Workstream: issue `#89`  
Enabled production connectors: **None**  
Secret accessed: **No**  
OAuth authorization performed: **No**  
External action performed: **No**

## Purpose

This baseline establishes the default-deny framework for official API/OAuth connectors and Google Secret Manager references.

The initial accepted production posture is zero enabled connectors. GitHub, Google Drive, and Gmail are candidate integrations only. Their definitions are disabled, have empty destination allowlists, possess unresolved Secret Manager references, and lack terms or staging evidence.

## Canonical artifacts

```text
config/production_connector_secret_broker.json
schemas/production_connector_secret_broker.schema.json
schemas/connector_action_request.schema.json
schemas/connector_action_approval.schema.json
schemas/connector_action_receipt.schema.json
schemas/connector_staging_receipt.schema.json
src/infrastructure/secrets/google_secret_manager.py
src/application/production_connectors.py
src/application/governed_production_connectors.py
```

## Secret Manager boundary

The resolver accepts only:

```text
gcp_secret://<project-id>/<secret-id>/<version>
```

It rejects before client creation when:

- access authority is false;
- the project remains `TBD_PROJECT`;
- the expected project is unset;
- the reference project is not allowlisted;
- the reference is malformed.

A successful access returns:

- in-memory byte material;
- canonical resource reference;
- accessed version name;
- access timestamp;
- confirmation that the raw value was not logged or persisted.

The material is held in a mutable byte buffer and zeroized when the context closes. Python and operating-system memory management cannot provide a universal physical-memory erasure guarantee, so the zeroization is defence in depth rather than a hardware attestation.

The repository never contains the resolved secret value.

## Connector inventory

### GitHub

Candidate authentication:

```text
GitHub App
```

Candidate operations:

- repository read;
- issue creation;
- pull-request comment.

Issue creation and pull-request commenting are consequential external writes and require request-bound accountable-operator approval.

### Google Drive

Candidate authentication:

```text
OAuth 2.0
```

Candidate operations:

- file search;
- managed file creation.

File creation is an external write and requires approval.

### Gmail

Candidate authentication:

```text
OAuth 2.0
```

Candidate operations:

- message search;
- draft creation;
- message send.

A Gmail draft changes a remote account and is therefore treated as an external write even though it does not send a message. Draft creation and sending both require approval; sending requires its own narrower scope.

## Dry-run request preparation

The browser or caller provides proposed payload content only to the internal preparation service.

The persisted/request evidence contains:

- exact revision;
- connector and operation IDs;
- allowlisted destination;
- idempotency key;
- payload digest;
- request digest;
- mode and consequence;
- approval scope;
- dry-run completion;
- timestamp.

It does not contain the payload body.

An exact 40-character Git revision and an allowlisted destination are mandatory before preparation.

## Action approval

Every operation with an approval scope requires a strict, short-lived approval bound to:

- request ID;
- request digest;
- exact revision;
- connector;
- operation;
- destination;
- approval scope;
- accountable-operator role;
- issue and expiry times.

The maximum approval lifetime is 15 minutes.

Changing the payload, destination, operation, connector, revision, or request digest invalidates the approval.

## Execution order

The governed broker checks, in order:

1. execution authority;
2. connector enablement;
3. official API status;
4. approved terms review;
5. verified staging evidence;
6. destination allowlist;
7. request-bound action approval where required;
8. adapter availability;
9. idempotency claim;
10. Secret Manager access;
11. adapter invocation;
12. result-digest and receipt generation;
13. secret-material zeroization.

No secret access occurs when any prior gate fails.

## Idempotency and uncertain writes

An idempotency key is stored only as a SHA-256 digest and bound to the exact request digest.

- identical replay is blocked;
- changed intent with the same key is blocked;
- a failed action after the adapter is invoked remains consumed because the remote side effect may be uncertain;
- manual or connector-specific reconciliation is required before any later retry.

This is intentionally conservative. It prevents duplicate messages, issues, comments, files, or drafts after an ambiguous transport failure.

## Evidence receipts

Receipts contain:

- request and idempotency digests;
- connector, operation, and destination;
- result and reason codes;
- approval ID where applicable;
- redacted Secret Manager access receipt;
- adapter result digest;
- timestamp;
- whether a consequential external action was performed or may have been performed.

They contain no connector payload and no credential material.

A write is marked `external_action_performed: true` only after the platform adapter is invoked. A Secret Manager failure before invocation does not claim a platform action.

## Current production state

Every connector has:

```text
enabled: false
destination_allowlist: []
staging_evidence_status: NOT_STARTED
terms_review_status: REQUIRED
```

The Secret Manager project ID is null and all references use `TBD_PROJECT`.

The evaluator therefore reports:

```text
implemented_internal: true
production_complete: false
enabled_connectors: []
```

## Required staging sequence per connector

After an operator selects a connector and separately authorizes staging preparation:

1. complete platform terms and permission review;
2. select the exact official API and authentication model;
3. define the minimum OAuth/GitHub App scopes;
4. create an isolated test account or repository/folder/mailbox;
5. define the exact test destination allowlist;
6. provision a Canada-replicated Secret Manager resource;
7. grant only the staging workload identity access;
8. observe secret-access audit logging;
9. test one read-only action;
10. prepare a write in dry-run mode;
11. issue a request-bound accountable-operator approval;
12. perform one approved test write to the test destination;
13. verify duplicate and changed-intent denial;
14. verify platform rate-limit handling;
15. revoke and rotate the credential;
16. disable the adapter and prove fail-closed behavior;
17. test provider outage behavior;
18. inspect logs, receipts, and persistence for payload or secret leakage;
19. emit a `connector_staging_receipt`;
20. obtain accountable-operator review.

Production accounts and destinations are prohibited in the staging receipt.

## Connector-specific cautions

### GitHub

- use a GitHub App rather than a broad personal token where feasible;
- installation and repository scope must be explicit;
- issue/comment writes must target an approved test repository;
- no repository administration, branch-protection change, merge, release, or secret-management permission is implied.

### Google Drive

- prefer file-specific or app-created-file scopes over broad Drive access;
- creation must occur only in an approved test folder;
- no deletion, ownership transfer, public sharing, or domain-wide access is implied.

### Gmail

- prefer metadata/read scopes for search and compose/draft scope for draft creation;
- send permission is a separately approved scope and action;
- no bulk messaging, automated outreach, reply impersonation, or hidden recipient behavior is permitted;
- destination allowlists and human review remain mandatory.

## Rollback and revocation

If connector behavior is unsafe or staging evidence fails:

- keep the connector disabled;
- revoke OAuth grants or GitHub App installation access if separately authorized;
- disable the workload identity permission to the relevant secret;
- rotate or destroy the staging credential;
- retain redacted request, approval, result, and audit receipts;
- reconcile any uncertain write at the provider before retrying;
- correct the implementation in a new reviewed revision.

Rollback never deletes or rewrites immutable connector evidence.

## Current blockers

```text
Secret Manager project ID
resolved connector secret references
connector terms reviews
approved test destinations
least-privilege scope manifests
staging OAuth/GitHub App authorization
secret-access audit observation
credential rotation/revocation evidence
GitHub staging receipt
Google Drive staging receipt
Gmail staging receipt
duplicate prevention staging evidence
redaction review
at least one operator-approved enabled production connector
```

## Readiness truth

This internal framework does not justify promoting `approved_external_connectors` from `planned` or removing it from production blocking gaps.

The accepted initial posture of zero enabled connectors is safe, but it is not evidence that an external connector capability is complete. A later evidence-only readiness PR requires at least one explicitly approved connector with a passing exact-revision staging receipt and separate production activation authority.
