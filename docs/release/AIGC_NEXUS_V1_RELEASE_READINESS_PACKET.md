# AIGC Nexus V1 Release Readiness Evidence Packet

Status: `SUPERSEDED HISTORICAL PACKET — NOT RELEASE AUTHORITY`

This packet predates the PR #181 release-closure security and CI repairs. It
must not be used to mark a PR ready, merge, deploy, call a provider, enable
traffic, or claim production completion. The repair branch requires a fresh
exact-head receipt. The current repository truth is recorded in
`docs/release/AIGC_NEXUS_V1_RELEASE_CLOSURE_REPAIR.md`.

## Latest admitted implementation baseline before this packet update

- repository: `Lornt1666/AIGC`
- PR: `#181`
- integration branch: `release/aigc-nexus-v1`
- pre-repair source head: `18e886d48c57b85d8ab8115a6fb765fa6e655fc9`
- pre-repair tested tree: `0835d1ec8c57a279c9839bfa207038042e22ed23`
- historical exact-head workflow: `AIGC CI #2758`
- historical workflow run ID: `31264978346`
- historical retained artifact ID: `9023893562`
- historical artifact digest: `sha256:84798f4a815eff7dbb4dfb462f01eee07fbaccc4973e20ceb8209aeea1af02f5`
- converged current-main parent: `60297f4c6ac1c0feecb5ab913991cf3220247f27`

The commit containing this packet requires its own fresh exact-head CI receipt. This packet is evidence, not authority.

## Constitutional release rule

`Reasoning != Verification != Authority != Execution != Evidence`

`Capability may evolve autonomously. Authority may not.`

No CI result, provider credential, provider output, Terraform plan, cloud receipt, repository content, memory record or evidence artifact grants authority by itself.

## Current completion matrix

| # | Required capability | Repository implementation | Empirical/external proof | Disposition |
|---|---|---|---|---|
| 1 | Private GitHub `READ_FILE` | Governed read transport implemented and one-shot canary previously exercised | Real transport path exercised; canonical RepositoryContext success receipt not retained | `TRANSPORT PROVEN / CANONICAL ADMISSION FAILED / NO RETRY` |
| 2 | GitHub production credential boundary | GitHub App boundary + keyless GitHub→Google WIF architecture implemented | Real GitHub App/WIF resources not yet provisioned | `IMPLEMENTED / EXTERNAL PROVISIONING REQUIRED` |
| 3 | Gemini adapter | Vertex Gemini adapter behind governed live runtime | No live Gemini receipt | `IMPLEMENTED + CI ADMITTED / NOT EXECUTED` |
| 4 | OpenAI adapter | Responses adapter, `store=false`, no tools, infrastructure-only credential callback | OpenAI project-key target/setup not completed in AIGC runtime | `IMPLEMENTED + CI ADMITTED / NOT EXECUTED` |
| 5 | Durable runtime controls | Transactional PostgreSQL stop epoch, idempotency, rate/usage budgets, permit counters and terminal replay | PostgreSQL 16 integration exercised in CI | `ADMITTED` |
| 6 | External identity / resource procurement | Expiring actor-bound procurement contract, read-only discovery, durable Terraform state bootstrap, saved-plan plan/apply gate, WIF/IAM, regional secret metadata and broker-receipt validation | Google account mutations and negative-permission checks not executed | `DOCUMENTED / ACCOUNT RECEIPTS REQUIRED` |
| 7 | Controlled live provider canaries | Canonical one-use Gemini/OpenAI plans, HUMAN GovernanceDecision, ExecutionPermit, detached KMS authority attestation, dedicated provider identities and execution-only launcher | Exact dormant jobs have no separate admitted provisioning receipt; no provider call executed | `REPOSITORY GAP + LIVE RECEIPTS ABSENT` |
| 8 | Immutable Québec staging | Exact CI admission plus six KMS action permits, predecessor-derived immutable SBOM target, regional build, provenance/scan checks, migration and private/no-traffic service controls | Fresh CI admission, scoped SBOM IAM and all cloud receipts absent | `NOT YET OPERATIONALLY ADMITTED` |
| 9 | Deployed load/security/reconciliation | Bounded authenticated validation harness implemented | No deployed candidate latency/load/security receipt | `HARNESS COMPLETE / NOT EXECUTED` |
| 10 | Release → ready → merge → post-merge | Release evidence and exact-head CI machinery implemented | External receipts remain incomplete | `DO NOT MARK READY / DO NOT MERGE` |

## Exact-head implementation evidence

At pre-repair head `18e886d48c57b85d8ab8115a6fb765fa6e655fc9`, AIGC CI #2758 passed the historical offline contract. That run did **not** validate the changed `infra/gcp/quebec` root and cannot admit the repair diff.

- exact requested checkout and tested-tree binding;
- dependency installation and `pip check`;
- Python compilation;
- complete repository tests with zero failed/error tests;
- PostgreSQL-backed Nexus runtime-control integration;
- external-procurement/WIF/state-backend/Terraform-plan regressions;
- Gemini/OpenAI canary planning and permit regressions;
- private staging/deployment/migration regressions;
- canonical contracts and provider-discovery guard;
- redaction scan with zero findings;
- release secret scan with zero findings;
- Terraform formatting/validation/inertness;
- Colosseum schema and round-trip validation;
- false-authority verification;
- readiness validation;
- local `Dockerfile.nexus` build as non-root user `aigc`.

The retained exact-head admission receipt states:

```text
external_authority_granted = false
live_model_call_authority_granted = false
deployment_authority_granted = false
financial_authority_granted = false
merge_authority_granted = false
```

Local container evidence states:

```text
registry_push_performed = false
cloud_build_performed = false
deployment_performed = false
```

## Verified external account metadata

Operator-owned Google account evidence has established these non-secret identifiers:

```text
project_id      = oceanic-base-485407-i7
project_number  = 170151535592
billing_account = 0156E0-2BDD06-7561F1
region          = northamerica-northeast1
```

This does **not** yet prove live project↔billing linkage, WIF provisioning, service-account existence, nonzero spend authority, or resource creation. The committed procurement packet therefore remains `template_only=true`, zero-spend and mutation-inert.

## External procurement architecture now implemented

The repository documents the intended fail-closed bridge from account access
to runtime evidence. It is not a proof that the bridge has executed, and the
current repair still has an unresolved dormant-canary-job provisioning gate.

```text
read-only project/billing discovery
        ↓
short-lived accountable procurement authority
        ↓
durable Montréal GCS Terraform state bootstrap
        ↓
exact material Terraform saved plan + SHA-256 receipt
        ↓
separately authorized apply of that exact saved plan
        ↓
keyless GitHub OIDC WIF + least-privilege service accounts
        ↓
regional Artifact Registry / private Cloud SQL / buckets / KMS / logs
        ↓
regional Secret Manager metadata
        ↓
broker-governed runtime DB credential and DSN creation
        ↓
exact regional DSN secret version
        ↓
remaining exact regional secret versions
        ↓
fresh exact-head CI admission
        ↓
six independent one-mutation KMS action permits
        ↓
regional Cloud Build with dedicated build identity
        ↓
immutable Artifact Registry digest
        ↓
SBOM + signed provenance + vulnerability-scan evidence
        ↓
private no-traffic Cloud Run candidate with Direct VPC egress
        ↓
one-task/no-retry runtime-control migration
        ↓
/ready=true
        ↓
separately admitted dormant Gemini and OpenAI Cloud Run Jobs
        ↓
one-use Gemini and OpenAI job executions
        ↓
canonical provider usage/latency/cost/ExecutionReceipt evidence
        ↓
bounded deployed validation
```

Key implementation surfaces:

- `config/aigc_external_release_procurement.example.json`
- `scripts/aigc_external_release_procurement.py`
- `scripts/bootstrap_quebec_terraform_state.py`
- `scripts/terraform_quebec_foundation.py`
- `infra/gcp/quebec/backend.tf`
- `infra/gcp/quebec/external_identity_and_secrets.tf`
- `scripts/bootstrap_nexus_runtime_database_secret.py`
- `scripts/provision_nexus_regional_secret_version.py`
- `src/operations/nexus_postgres_migrate.py`
- `src/operations/nexus_provider_canary.py`
- `scripts/launch_nexus_provider_canary_job.py`
- `scripts/deploy_nexus_staging.py`
- `scripts/validate_nexus_staging_runtime.py`
- `docs/release/AIGC_EXTERNAL_RUNTIME_PROCUREMENT_RUNBOOK_V1.md`

## Keyless identity and secret law

The Google WIF provider is restricted to:

```text
repository          = Lornt1666/AIGC
repository_id       = 1287333065
repository_owner_id = 236225491
allowed branch ref  = main
workflow            = aigc-release-staging.yml on main
event/environment   = workflow_dispatch / aigc-nexus-staging
OIDC issuer         = https://token.actions.githubusercontent.com
```

No Google service-account key resource is created.

The provider federates only the read-only `security_review` account. The
the repository deployer is read-only, and provider-capable canary identities are not federated;
this is an intentional fail-closed boundary until a permit-enforcing execution
broker is separately reviewed and proven live.

Regional secret **containers** are Terraform-managed, but secret **versions** are outside Terraform so raw values cannot enter Terraform state. Exact versions are created only through Omega-X → Ultra-Secrets Agent → Secret Broker → Google Cloud Secret Manager. Repository tools accept sanitized broker receipts and never accept raw values.

The Cloud SQL runtime password and socket DSN must never enter agent-visible memory. The Secret Broker performs the coupled database-user/version operation and returns only exact enabled numeric-version metadata. Partial cross-service outcomes require reconciliation and no blind retry.

## Terraform state and apply law

The Québec root now declares a GCS backend without a committed bucket name. The state bucket is bootstrapped as a separate governed phase with Montréal location, uniform bucket-level access, public-access prevention, versioning, retention and soft-delete controls.

A material Terraform plan requires reviewed resource-creation intent but performs no apply. Its receipt binds the backend, procurement packet, resource manifest and exact saved-plan SHA-256.

Terraform apply is separately authorized and can consume only that exact saved plan. Destroy/replacement actions are prohibited by the current gate. A failed apply is indeterminate and is not automatically retried.

## Live provider canary law

Each provider receives a different one-use permit.

A canary requires:

```text
GovernanceDecision.decision = approved
GovernanceDecision.authority_source = HUMAN
exact MAX_COST_CAD condition
ExecutionPermit.maximum_invocations = 1
exact principal/capability/resource/revision/request-digest binding
exact regional runtime-control secret reference
exact regional OpenAI key reference for OpenAI only
durable PostgreSQL runtime-control health
short-lived detached KMS authority attestation
exact pre-admitted dormant job name and configuration
```

The canary jobs use the same immutable candidate image and private Cloud SQL
execution plane, with distinct provider identities:

```text
tasks = 1
parallelism = 1
max_retries = 0
Direct VPC egress = private-ranges-only
Gemini service account = <resource-prefix>-can-gem@<project>.iam.gserviceaccount.com
OpenAI service account = <resource-prefix>-can-oai@<project>.iam.gserviceaccount.com
launcher job deployment = false
```

The retained canary receipt removes provider response text but retains provider request ID, response digest, latency, usage, cost, ExecutionReceipt and audit counters.

## Private GitHub read canary reconciliation

The earlier one-shot private-GitHub canary remains consumed. It exercised the real read-only transport path but did not retain a canonical successful RepositoryContext receipt. Its disposition remains:

```text
TRANSPORT PROVEN
CANONICAL ADMISSION FAILED
AUTOMATIC RETRY = false
```

## Remaining external blockers

The repository still lacks both empirical account/runtime receipts and a
complete executable closure for every mutation boundary:

1. fresh successful inner exact-head CI evidence for the repair head and tree;
2. independent repository review and separate code-integration authority;
3. after merge, successful protected-main CI plus an automatically assembled
   `aigc.exact-head-ci-admission.v2` packet;
4. authenticated live confirmation that project `oceanic-base-485407-i7` is linked to billing account `0156E0-2BDD06-7561F1`;
5. explicit reviewed nonzero CAD staging/canary spend ceiling and current pricing review;
6. completed GitHub source-control credential preflight;
7. state-backend bootstrap receipt;
8. exact Terraform plan and separately authorized successful foundation apply receipt;
9. real WIF/service-account/resource and negative-permission reconciliation receipts;
10. exact Montréal runtime DSN and other required enabled numeric secret-version receipts;
11. completed secure OpenAI project key provisioning and exact regional secret-version receipt;
12. six independently signed one-mutation staging action permits and atomic consumption receipts;
13. a least-privilege create-only receipt-bucket grant and narrowly scoped SBOM-export grant, with no broad Storage Admin substitution;
14. real regional Cloud Build ID, immutable Artifact Registry digest, SBOM, signed provenance and scan receipt;
15. successful runtime migration plus private no-traffic operator/judge revision and authenticated health/readiness receipts;
16. separately admitted dormant Gemini/OpenAI jobs using their dedicated service accounts;
17. one successful governed Gemini canary receipt;
18. one successful governed OpenAI canary receipt;
19. real deployed latency/load/security validation receipt;
20. any separately authorized fault-injection receipt required by final release review.

No placeholder may be promoted into evidence.

## Release disposition

```text
repository_architecture_converged = false
current_main_ancestry_converged = HISTORICAL_ONLY
external_procurement_implementation = DOCUMENTED_NOT_EXECUTED
keyless_wif_implementation = DOCUMENTED_NOT_RECONCILED
durable_terraform_state_implementation = COMPLETE
saved_plan_apply_gate = COMPLETE
regional_secret_versioning_implementation = BROKER_RECEIPT_VALIDATION_ONLY
runtime_database_bootstrap_implementation = BROKER_EXECUTION_REQUIRED
provider_canary_execution_implementation = BLOCKED_ON_DORMANT_JOB_ADMISSION
immutable_staging_deployment_implementation = DOCUMENTED_NOT_EXECUTED
deployed_validation_harness = COMPLETE
local_nexus_container_build = SUPERSEDED_BY_REPAIR_DIFF

fresh_repair_exact_head_ci = NOT_EXECUTED
live_google_account_discovery = NOT_EXECUTED
wif_and_foundation_apply = NOT_EXECUTED
live_gemini_canary = NOT_EXECUTED
live_openai_canary = NOT_EXECUTED
staging_cloud_deployment = NOT_EXECUTED
deployed_load_security_validation = NOT_EXECUTED
production_activation = false
ready_for_review = false
merge_authority = false
```

Therefore:

`RELEASE_GATE_AIGC_NEXUS_V1_FINAL = BLOCKED_ON_REPAIR_ADMISSION_AND_EXTERNAL_RUNTIME_EVIDENCE`

PR #181 MUST remain draft under the current authorization. A later code merge
requires independent review and explicit merge authority, but it must not be
misrepresented as `RELEASED_NO_TRAFFIC`. Cloud release still requires every
external receipt above and the post-merge protected-main admission packet.
