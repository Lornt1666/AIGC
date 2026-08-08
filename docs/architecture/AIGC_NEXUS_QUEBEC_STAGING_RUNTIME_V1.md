# AIGC Nexus V1 Québec Staging Runtime and Validation

Status: `IMPLEMENTED INERT DEPLOYMENT SURFACE — EXTERNAL STAGING AUTHORIZATION/IDENTITY REQUIRED`

## Purpose

This increment makes Gates 7–8 repository-code complete without manufacturing cloud facts or performing a provider call. Actual deployment remains governed by `aigc.quebec-cloud-authorization.v1` at `gate=staging` and therefore requires verified project/billing/resource identities, completed reviews, exact regional secret versions, unexpired staging authority, and the exact approval phrase.

## Runtime topology

```text
Cloud Run candidate (no traffic, authenticated)
        ↓
AIGC Nexus Runtime API
        ├── /health          process-only, no secret/provider access
        ├── /ready           exact release + immutable digest + regional secret ref + durable Postgres health
        └── /observability   metadata-only counters; no secret values
        ↓
RegionalSecretManagerResolver
        ↓
secretmanager.northamerica-northeast1.rep.googleapis.com
        ↓
exact numeric runtime_control_dsn secret version
        ↓
PostgresRuntimeControlStore.healthcheck()
```

Regional secret **values are not injected into Cloud Run configuration**. The deployment passes only an exact non-secret resource reference. The service identity resolves that value at runtime through the Montréal regional Secret Manager endpoint using Google managed identity/ADC. This preserves the regional-secret architecture while keeping raw values out of deployment commands, environment manifests, receipts, prompts, and repository state.

## Container

`Dockerfile.nexus` is a Python 3.12 non-root image and contains only the runtime source plus exact direct dependencies. It starts `src.webapp.nexus_runtime_api:app` on port 8080 and has a process-level `/health` container health check.

`.gcloudignore.nexus` excludes repository history, local environments, credential files, reports, tests, infrastructure plans, migrations, configuration, and generated evidence from the build context. It does not use broad filename patterns that would accidentally exclude credential-boundary source code.

## Build and immutable image

`cloudbuild.nexus.yaml` builds and publishes one explicit `_IMAGE_URI`.

`scripts/deploy_nexus_staging.py`:

1. validates the existing Québec authorization and exact resource manifest at `gate=staging`;
2. requires checkout SHA and tree to equal the authorized release;
3. performs read-only prerequisite checks for Artifact Registry, Cloud SQL and operator service identity;
4. submits Cloud Build in `northamerica-northeast1`;
5. resolves the pushed image to `sha256:<digest>`;
6. deploys Cloud Run using the immutable digest, not the mutable build tag;
7. uses the operator service account and private Cloud SQL attachment;
8. disables unauthenticated access and deploys with `--no-traffic` under a candidate tag;
9. configures startup, liveness and readiness HTTP probes;
10. keeps live-provider and production activation flags false;
11. probes `/ready` with an identity token after deployment;
12. persists an immutable deployment receipt.

A non-zero mutating `gcloud` command is treated as an indeterminate cloud-mutation outcome. The script does not automatically retry it.

## Health and readiness semantics

`/health` proves only that the process is alive. It never accesses Secret Manager, PostgreSQL or a model provider.

`/ready` fails closed unless:

- `AIGC_RELEASE_REVISION` is an exact 40-character Git SHA;
- `AIGC_IMAGE_DIGEST` is an immutable SHA-256 image digest;
- region equals `northamerica-northeast1`;
- the runtime-control DSN is referenced by an exact numeric Montréal Secret Manager version;
- regional Secret Manager resolution succeeds;
- `PostgresRuntimeControlStore.healthcheck()` reports `ok=true` and `durable=true`.

The secret value is cached only indirectly inside the initialized Postgres control-store object; the local string variable is cleared after construction and is never returned by the API.

## Deployed validation harness

`scripts/validate_nexus_staging_runtime.py` is a bounded, read-only staging verification client. With an authenticated candidate URL it checks:

- authenticated `/health`;
- authenticated `/ready`;
- metadata-only `/observability`;
- unauthenticated access denial;
- authenticated unknown-route fail-closed behavior;
- bounded concurrent readiness load (1–200 requests, concurrency 1–20);
- mean, p50, p95 and max observed latency;
- zero load failures;
- canonical local indeterminate-receipt reconciliation semantics.

It does **not** perform destructive deployed fault injection and does not call Gemini/OpenAI. A separate controlled fault-injection authorization is required before deliberately stopping a staging dependency or activating the durable emergency stop in deployed infrastructure.

## Authority boundary

This implementation grants no Google Cloud project identity, billing authority, resource-creation authority, provider-call authority, financial authority, production activation, traffic migration or merge authority.

Repository status after implementation may truthfully be described as:

```text
nexus_staging_runtime_implemented = true
immutable_digest_deployment_procedure_implemented = true
health_readiness_observability_implemented = true
deployed_validation_harness_implemented = true
actual_staging_deployment = false unless a deployment receipt proves otherwise
actual_deployed_load_validation = false unless a validation receipt proves otherwise
live_model_call_performed = false
production_activation = false
```
