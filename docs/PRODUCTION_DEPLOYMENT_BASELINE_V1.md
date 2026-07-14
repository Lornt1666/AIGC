# Production Deployment Baseline v1

Status: `IMPLEMENTED_INTERNAL_PENDING_ENVIRONMENT_AND_STAGING_EVIDENCE`  
Parent: issue `#83`  
Workstream: issue `#90`  
Resources created: **No**  
Terraform applied: **No**  
DNS changed: **No**  
Deployment performed: **No**

## Purpose

This baseline fixes the accepted Google Cloud deployment topology and makes every current plan fail closed. It defines no Google Cloud resources. The Terraform module contains version constraints, inputs, topology, outputs, and release guardrails only.

## Connector dependency synchronization

This deployment train is stacked above connector and Secret Manager PR `#98`.

The deployment branch is now rebased directly on the reviewed upstream correction head:

```text
upstream PR: #98
upstream head: 1b08f5e698ce69270a44b74d82a19fc041e20760
rollback branch: codex/production-deployment-baseline-v1-pre-sync-rebase
```

The synchronized boundary enforces the same Google Cloud project-ID grammar in:

- Secret Manager reference parsing;
- connector staging receipt validation;
- deployment plan evaluation;
- connector and deployment boundary tests.

Valid project IDs are 6–30 characters, begin with a lowercase letter, contain only lowercase letters, digits, or hyphens, and end with a lowercase letter or digit. `TBD_PROJECT` remains allowed only as the explicit unresolved marker in disabled connector configuration; it is not valid staging or deployment evidence.

This synchronization does not merge PR `#98`, activate any connector, access Secret Manager, authorize Terraform, create a cloud resource, or deploy AIGC.

## Accepted topology

- Cloud Run v2 in Toronto;
- external HTTPS load balancer and managed TLS;
- Cloud Armor required;
- private Cloud SQL PostgreSQL connectivity;
- Montréal recovery region;
- Google Secret Manager with workload identity;
- immutable container by SHA-256 digest;
- non-root runtime;
- startup/liveness/readiness health path `/health`;
- canary rollout at 5% for 30 minutes;
- automatic rollback on health failure;
- CAD 200 monthly ceiling and 50/80/100 percent alerts;
- RPO 15 minutes and RTO 4 hours.

## Current unresolved inputs

```text
staging project ID
production project ID
production domain
workload service account
network reference
Cloud SQL instance reference
Secret Manager project
immutable image reference and digest
release-gate receipt
technical alert recipient
Terraform remote state backend
```

## Terraform guard

`infra/terraform/gcp` defaults to:

```text
resource_creation_authorized = false
release_gate_result = DENY
deployment_authorized = false
```

Resource creation may later be requested only when all of the following are bound:

- exact 40-character Git revision;
- immutable image digest;
- valid project ID;
- production domain for production;
- candidate-bound production release-gate receipt;
- gate result `PERMIT`;
- deployment authorization.

The current module defines no `google_*` resources. Later reviewed resource modules must use `local.resource_creation_effective` and may not bypass `guardrails.tf`.

## Executable plan evaluator

`src/core/production_deployment_plan.py` validates:

- deployment baseline schema;
- Terraform fingerprint and required guard fragments;
- absence of Google Cloud resources in the no-resource baseline;
- the complete strict `production_release_gate_receipt` contract before trusting any gate field;
- exact revision, image, project, domain, and release receipt;
- gate revision/artifact binding;
- staging or production authority.

An incomplete dictionary, an unknown field, or a contract-inconsistent `PERMIT` is classified as `RELEASE_GATE_RECEIPT_INVALID`. No unvalidated gate identifier is copied into the deployment receipt.

The real configuration returns `DENY`. A fully bound synthetic staging candidate may return `PLAN_ELIGIBLE`, but its receipt always records:

```text
resource_creation_effective: false
external_action_performed: false
```

Plan eligibility is not an apply permit.

## Future staging evidence

A passing `staging_deployment_receipt` requires:

- immutable signed image;
- SBOM and provenance;
- non-root runtime;
- migration and health checks;
- complete identity → authorization → Quest → review journey;
- logs, metrics, alerts, and budget alarms;
- canary success;
- rollback readiness;
- database restore;
- Secret Manager access audit;
- no production data.

## Rollback

A rollback must bind failed and restored revisions and image digests, preserve audit evidence, record the database action, and prove restored health.

If schema compatibility is uncertain, do not point the prior application at the modified database. Restore to an isolated database, verify integrity, then promote only under a reviewed recovery procedure.

## Required next sequence

After project IDs, domain, technical contact, and explicit resource authority exist:

1. add reviewed Google Cloud resource modules;
2. configure isolated staging remote state;
3. create staging project resources only;
4. build immutable image with SBOM/provenance/signature;
5. run release gate for exact staging candidate;
6. apply staging plan under concurrency lock;
7. run migrations and health/synthetic journeys;
8. test alerts, canary, rollback, and database restore;
9. emit staging deployment and rollback receipts;
10. obtain accountable-operator review;
11. promote readiness only through a separate evidence PR.

Production remains blocked until issue #91 produces a fresh candidate-bound release-gate `PERMIT`.
