# PIBC Authorization and Quest Bridge v1

Status: stacked implementation candidate on top of PIBC-v1.  
Base dependency: draft PR #80, exact head `96c1c7d1198246df13a9a5495891e8fcdc460666`.  
External action performed: No.  
Production identity configured: No.

## Purpose

This bridge completes the governed local work-acceptance chain without creating a second authorization kernel or Quest lifecycle service.

```text
repository-owned local identity fixture
→ PIBC-v1 local preflight
→ immutable PIBC receipt
→ IdentityAuthorizationBridge
→ existing PrincipalAuthorityBindingKernel
→ immutable authorization receipt
→ existing QuestApplicationService.accept_work
→ repository-controlled Quest transition
→ append-only audit evidence
```

## Trust rule

The browser never supplies:

- principal identity;
- tenant or project authority;
- membership or session authority;
- roles or scopes;
- assurance levels;
- authorization policy;
- an authorization request;
- provider claims, tokens, nonce values, or credentials.

The browser receives an opaque PIBC receipt ID and submits only that ID with the expected Quest revision, accountable-operator role, and optional reason.

## Application services

### LocalOperatorIdentityPreflightService

- requires `APPROVAL_REQUIRED` and a pending approval request;
- validates the expected Quest revision;
- selects exactly one active local operator binding from the repository-owned fixture;
- derives a deterministic assertion identifier from trusted binding IDs and the approval revision;
- invokes PIBC-v1 in local mode;
- returns only a persisted local-simulation identity receipt;
- cannot claim production identity.

### IdentityAuthorizationBridge

- retrieves the identity receipt from append-only persistence;
- requires a non-expired PIBC `PERMIT`;
- requires principal, membership, session, tenant, project, assurance, evidence maturity, and runtime authority bindings;
- requires the PIBC revision to equal the pending Quest approval revision;
- reloads matching trusted authority records from the local fixture;
- builds the existing authorization request through `QuestApplicationService`;
- binds `AIGC-PIBC-RECEIPT:<receipt-id>` into authorization evidence;
- invokes the existing `AuthorizationApplicationService` and kernel;
- requires a persisted authorization `PERMIT`;
- performs no Quest transition itself.

### IdentityBoundWorkAcceptanceHandler

- coordinates the bridge with the existing Quest service;
- passes the persisted authorization receipt and exact authorization request to the existing `accept_work` transition;
- never mutates Quest state directly;
- preserves optimistic concurrency, idempotency, schema validation, transition receipts, and audit events;
- supports identical replay only when the stored authorization receipt remains bound to the same PIBC receipt.

## API

### Local identity preflight

```text
POST /api/v1/quests/{quest_id}/local-identity-preflight
```

Request:

```json
{
  "expected_revision": 2,
  "operator_role": "ACCOUNTABLE_OPERATOR"
}
```

The route accepts no identity or authority fields.

### Identity-bound work acceptance

```text
POST /api/v1/quests/{quest_id}/identity-bound-accept-work
```

Request:

```json
{
  "expected_revision": 2,
  "identity_receipt_id": "IDR-AAAAAAAAAAAAAAAAAAAAAAAA",
  "operator_role": "ACCOUNTABLE_OPERATOR",
  "reason": "Proceed with bounded internal work."
}
```

The request contract is `schemas/identity_bound_work_acceptance.schema.json`.

## Quest Board

The button sequence is now:

```text
operator confirmation
→ local identity preflight
→ opaque PIBC receipt ID
→ identity-bound acceptance command
→ server-side authorization
→ canonical Quest transition
```

The browser no longer downloads, modifies, or submits authorization bundles.

## Evidence chain

The final Quest record references the immutable authorization receipt. The authorization receipt contains:

```text
AIGC-PIBC-RECEIPT:<identity-receipt-id>
```

in its evidence IDs. The authorization receipt also remains bound to:

- exact repository revision;
- principal, membership, and session;
- tenant and project;
- target Quest resource;
- `accept_work` action;
- `quest:work_accept` scope;
- `work_acceptance` purpose;
- approval-request and transition-digest evidence.

## Non-scope

This bridge does not configure live OIDC, workload identity, credentials, hosted login, deployment, external connectors, contract acceptance, application submission, messaging, payment, delivery, or other external action.

It does not promote `production_identity_access` in the readiness ledger. It proves a local identity-bound integration path only.

## Verification gates

- strict command-schema tests;
- local preflight state and revision tests;
- forged or missing PIBC receipt denial;
- caller-supplied authority rejection;
- authorization evidence binding;
- canonical Quest transition and restart persistence;
- idempotent identical command replay;
- existing authorization and Quest regression tests;
- contract, constitutional, redaction, procurement-smoke, full-test, and readiness CI gates.
