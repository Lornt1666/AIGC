# AIGC Nexus V1 Release Readiness Evidence Packet

Status: `REPOSITORY RELEASE-CANDIDATE COMPLETE — EXTERNAL RUNTIME EXECUTION STILL REQUIRED`

## Latest admitted implementation baseline before this packet update

- repository: `Lornt1666/AIGC`
- PR: `#181`
- integration branch: `release/aigc-nexus-v1`
- admitted implementation head: `0c18b357644aeca732f67aad26294bab300d9adf`
- tested tree: `9b06b1c6185697d618d504000c3c80129bf7383b`
- exact-head workflow: `AIGC CI #2754`
- workflow run ID: `31264631721`
- retained artifact ID: `9023796536`
- retained artifact digest: `sha256:59089fa8823d725ac1494b3f513beeb4f5372a4954ae92fd7875f8ca160403f0`
- local Nexus image ID: `sha256:33fab3d5139392e839d7f870c944d1b8141a3e47b018d76bd4da4d4768ec4cc8`
- local container user: `aigc`
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
| 6 | External identity / resource procurement | Expiring actor-bound procurement contract, read-only discovery, durable Terraform state bootstrap, saved-plan plan/apply gate, WIF/IAM, regional secret metadata and exact-version tooling | Google account mutations not executed | `IMPLEMENTATION COMPLETE / ACCOUNT EXECUTION REQUIRED` |
| 7 | Controlled live provider canaries | Canonical one-use Gemini/OpenAI canary plans, HUMAN GovernanceDecision + ExecutionPermit validation, Cloud Run one-task/no-retry launcher, durable receipts | No provider API call executed | `IMPLEMENTATION COMPLETE / LIVE RECEIPTS ABSENT` |
| 8 | Immutable Québec staging | Regional Cloud Build, dedicated build identity, immutable digest, private/no-traffic Cloud Run, Direct VPC egress, private Cloud SQL, runtime migration, health/readiness/observability | No real Cloud Build / Artifact Registry / Cloud Run receipt | `IMPLEMENTATION COMPLETE / DEPLOYMENT NOT EXECUTED` |
| 9 | Deployed load/security/reconciliation | Bounded authenticated validation harness implemented | No deployed candidate latency/load/security receipt | `HARNESS COMPLETE / NOT EXECUTED` |
| 10 | Release → ready → merge → post-merge | Release evidence and exact-head CI machinery implemented | External receipts remain incomplete | `DO NOT MARK READY / DO NOT MERGE` |

## Exact-head implementation evidence

At `0c18b357644aeca732f67aad26294bab300d9adf`, AIGC CI #2754 passed:

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

The repository now provides the complete fail-closed bridge from account access to runtime evidence:

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
runtime DB credential generated only in process memory
        ↓
exact regional DSN secret version
        ↓
remaining exact regional secret versions
        ↓
regional Cloud Build with dedicated build identity
        ↓
immutable Artifact Registry digest
        ↓
private no-traffic Cloud Run candidate with Direct VPC egress
        ↓
one-task/no-retry runtime-control migration
        ↓
/ready=true
        ↓
one-use Gemini and OpenAI Cloud Run Jobs
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
allowed branch refs = release/aigc-nexus-v1 OR main
OIDC issuer         = https://token.actions.githubusercontent.com
```

No Google service-account key resource is created.

Regional secret **containers** are Terraform-managed, but secret **versions** are outside Terraform so raw values cannot enter Terraform state. Exact versions are created only through bounded provisioning tools and receipts contain references/digests, not values.

The Cloud SQL runtime password is generated in process memory. The socket-based DSN is written directly to Montréal regional Secret Manager and the runtime database user is created through the Cloud SQL Admin API. Partial cross-service outcomes require reconciliation and no blind retry.

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
```

The canary job uses the same immutable candidate image and private Cloud SQL execution plane, with:

```text
tasks = 1
parallelism = 1
max_retries = 0
Direct VPC egress = private-ranges-only
service account = operator
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

The repository no longer lacks a procedure for the remaining release work. It still lacks the **empirical account/runtime receipts** themselves:

1. authenticated live confirmation that project `oceanic-base-485407-i7` is linked to billing account `0156E0-2BDD06-7561F1`;
2. explicit reviewed nonzero CAD staging/canary spend ceiling and current pricing review;
3. completed GitHub source-control credential preflight;
4. state-backend bootstrap receipt;
5. exact Terraform plan and separately authorized successful foundation apply receipt;
6. real WIF/service-account/resource reconciliation receipt;
7. exact Montréal runtime DSN and other required secret-version receipts;
8. completed secure OpenAI project key provisioning and exact regional secret-version receipt;
9. real regional Cloud Build ID, immutable Artifact Registry digest and no-traffic Cloud Run revision;
10. successful runtime migration + authenticated health/readiness receipt;
11. one successful governed Gemini canary receipt;
12. one successful governed OpenAI canary receipt;
13. real deployed latency/load/security validation receipt;
14. any separately authorized fault-injection receipt required by final release review.

No placeholder may be promoted into evidence.

## Release disposition

```text
repository_architecture_converged = true
current_main_ancestry_converged = true
external_procurement_implementation = COMPLETE
keyless_wif_implementation = COMPLETE
durable_terraform_state_implementation = COMPLETE
saved_plan_apply_gate = COMPLETE
regional_secret_versioning_implementation = COMPLETE
runtime_database_bootstrap_implementation = COMPLETE
provider_canary_execution_implementation = COMPLETE
immutable_staging_deployment_implementation = COMPLETE
deployed_validation_harness = COMPLETE
local_nexus_container_build = PASS

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

`RELEASE_GATE_AIGC_NEXUS_V1_FINAL = BLOCKED_ONLY_ON_EXTERNAL_RUNTIME_EVIDENCE`

PR #181 MUST remain draft and unmerged until the missing external receipts are obtained or the declared V1 release scope is formally amended by a separately reviewed governance decision.
