# AIGC Production Finalization Program v1

Tracking issue: `#83`  
Foundation merged: PRs `#80`, `#81`, and `#82`  
Current readiness threshold: `90 / 100`  
Deployment default: **denied**

> Procurement grants direction. Implementation supplies substance. Verification supplies proof. The operator grants authority.

## Purpose

This program converts the governed local AIGC baseline into a production release candidate without allowing plans, source files, or self-reported scores to masquerade as production evidence.

Production is finalized only when the canonical readiness ledger reports:

```text
score >= 90
blocking_gaps == []
production_ready == true
```

and a candidate-bound accountable-operator approval causes the production release gate to emit `PERMIT` at the same exact revision.

A merged feature is not a deployment. A passing test is not live operational proof. A release-gate receipt performs no external action.

## Integrated baseline

The following governed foundation is now merged into `main`:

1. **PIBC-v1** — provider-neutral identity boundary, immutable redacted identity receipts, tenant/project/session controls.
2. **Identity-to-authorization bridge** — persisted PIBC evidence bound to the existing authorization kernel and Quest work-acceptance transition.
3. **Review Evidence Packet v1** — append-only evidence packets and accountable human judgment for `ACCEPTED_FOR_DELIVERY` or `REWORK_REQUIRED`.

These components establish the control plane. They do not complete live authentication, managed persistence, approved connectors, or production deployment.

## Canonical blockers

The production readiness ledger currently treats these capabilities as blocking:

- `security_privacy_wiring`
- `transactional_persistence`
- `production_identity_access`
- `approved_external_connectors`
- `production_deployment`

The ledger remains the source of truth. Capability status changes require executable and operational evidence, not a narrative update.

## Production Release Gate v1

Policy:

```text
config/production_release_gate.json
```

Contracts:

```text
schemas/production_release_gate_policy.schema.json
schemas/production_release_manifest.schema.json
schemas/production_release_operator_approval.schema.json
schemas/production_release_gate_receipt.schema.json
```

Evaluator:

```text
src/core/production_release_gate.py
```

The evaluator recalculates readiness directly from:

```text
config/production_readiness_ledger.json
```

It does not accept a readiness score in the release manifest.

### Required manifest evidence

A production release manifest must bind:

- exact 40-character Git revision;
- canonical readiness-truth digest;
- empty expected blocking-gap set;
- immutable release-artifact reference and SHA-256 digest;
- exact-head CI receipts;
- security-review receipts;
- privacy-review receipts;
- database restore receipts;
- rollback drill receipts;
- monitoring receipts;
- incident-response exercise receipts;
- candidate-bound accountable-operator approval;
- a short, expiring manifest lifetime;
- `external_action_performed: false`.

### Candidate-bound operator approval

The operator approval is not a bare string. It is a strict receipt bound to:

- release ID;
- exact revision;
- digest of the release candidate excluding the approval object;
- accountable-operator role;
- explicit `APPROVED` or `DENIED` decision;
- reason;
- issuance and expiry times;
- production-deployment authorization boolean;
- `external_action_performed: false`.

Changing the artifact, evidence receipts, revision, environment, readiness digest, or release ID after approval changes the candidate digest and invalidates the approval.

### Gate result

The gate emits an immutable JSON receipt with:

- actual recalculated readiness score;
- actual blocking gaps;
- exact revision;
- manifest digest;
- release-candidate digest;
- readiness-truth digest;
- release-artifact digest;
- operator approval receipt ID;
- reason codes;
- `deployment_authorized`;
- `external_action_performed: false`.

`deployment_authorized` is true only when every gate passes.

Run from the repository root:

```bash
python -m src.core.production_release_gate \
  --manifest path/to/production-release-manifest.json \
  --write \
  --require-permit
```

Exit code `3` means the candidate was denied. The command never deploys.

## Closure sequence

### Phase 0 — Release gate

Exit evidence:

- strict contracts;
- fail-closed evaluator;
- tests proving caller-supplied scores are rejected;
- tests proving current AIGC remains denied;
- tests proving a fully evidenced synthetic candidate can be permitted.

### Phase 1 — Security and privacy completion

Implement and verify:

- production threat model and trust-boundary inventory;
- privacy impact, retention, deletion, export, and access procedures;
- secure HTTP headers, CORS, CSRF, rate limiting, request-size limits, and timeout policy;
- redacted structured logging and append-only audit retention;
- dependency, software-bill-of-materials, image, and vulnerability evidence;
- incident-response exercise and recovery receipt;
- independent review findings resolved or explicitly accepted.

No capability promotion occurs until operational evidence exists.

### Phase 2 — Transactional production persistence

Implement and verify:

- managed relational database decision;
- persistence portability contract;
- production adapter and connection management;
- migration locking and safe retry behavior;
- transaction isolation and concurrent lifecycle tests;
- encrypted backup and point-in-time recovery;
- restore drill with integrity receipt;
- retention and append-only evidence preservation.

SQLite remains valid for bounded local operation but is not, by itself, production service evidence.

### Phase 3 — Production identity and tenant isolation

Implement and verify:

- explicit OIDC or workload-identity provider decision;
- signature and JWKS verification;
- issuer, audience, expiry, replay, and revocation checks;
- server-owned session storage and rotation;
- trusted membership, role, and scope resolution;
- cross-tenant and cross-project negative tests;
- staging login, logout, revocation, and recovery evidence;
- secret references only—no credentials in source, logs, prompts, or receipts.

PIBC remains the boundary; provider integration must not replace it.

### Phase 4 — Approved connectors and secret broker

Implement and verify each connector independently:

- platform terms and permission record;
- least-privilege OAuth scopes;
- approved secret manager integration;
- allowlisted destinations;
- dry-run and human-review mode;
- idempotency, retries, revocation, and audit receipts;
- explicit distinction between internal preparation and outward action.

No generic credential automation, platform bypass, or unrestricted scraping is authorized.

### Phase 5 — Reproducible deployment and operations

Implement and verify:

- hardened non-root container;
- immutable image digest and provenance;
- infrastructure-as-code for isolated staging and production environments;
- managed database and secret references;
- health, readiness, metrics, logs, alerts, and service objectives;
- migration orchestration;
- canary or equivalent safe rollout;
- rollback and disaster-recovery drill;
- environment separation and least-privilege runtime identity.

A staging deployment is evidence. It is not production authorization.

### Phase 6 — Final release candidate

At one exact revision:

1. run full CI;
2. generate the canonical readiness report;
3. verify score at least 90 and no blocking gaps;
4. assemble the immutable release artifact;
5. attach all required operational receipts;
6. compute readiness-truth and release-candidate digests;
7. obtain accountable-operator approval for that exact candidate;
8. run the production release gate;
9. deploy only when the gate emits `PERMIT`;
10. record deployment, health, and rollback receipts separately.

## Live decisions still required

The following cannot be inferred safely from source code:

- identity provider and tenant model;
- cloud account/project and region;
- production domain and TLS ownership;
- managed database service;
- secret-manager project and access policy;
- approved connector list and OAuth owners;
- data residency and retention requirements;
- backup recovery-point and recovery-time objectives;
- operational contacts and incident escalation path.

These decisions must be explicit, documented, and reviewed before their corresponding live integrations are activated.

## Non-authorizations

This program and release gate do not, by themselves, authorize:

- production deployment;
- credential creation or use;
- live identity-provider configuration;
- connector activation;
- applications, bids, contracts, messages, payments, delivery, or publication;
- Omega-X outward action;
- readiness-ledger promotion without evidence.

The release gate supplies a decision. The operator supplies final authority. The deployment system supplies the external action only after both are valid.
