# AIGC Nexus V1 External Runtime Procurement Runbook

Status: `IMPLEMENTED PROCEDURE — ACCOUNT-LEVEL EXECUTION STILL REQUIRES AUTHENTICATED GOOGLE/OPENAI ACCESS`

This runbook closes the gap between the exact-head repository release candidate and the missing external runtime receipts. It does **not** itself grant cloud, provider, spend, deployment, merge, or production authority.

## Verified external identity facts

The currently evidenced Google account facts are:

```text
project_id      = oceanic-base-485407-i7
project_number  = 170151535592
billing_account = 0156E0-2BDD06-7561F1
region          = northamerica-northeast1
```

The committed procurement example remains `template_only=true`, zero-spend, and mutation-inert. Copy it outside the repository into an operator-controlled evidence directory before changing any execution field.

## Architecture

```text
Authenticated bootstrap operator / Cloud Shell
        ↓
read-only project ↔ billing discovery receipt
        ↓
reviewed nonzero CAD ceiling + accountable expiring authority
        ↓
regional GCS Terraform state bootstrap
        ↓
exact material Terraform plan + retained plan digest
        ↓
separate saved-plan Terraform apply
        ↓
Québec foundation
        ├── regional Artifact Registry
        ├── private PostgreSQL Cloud SQL
        ├── regional buckets / KMS / logs
        ├── least-privilege service accounts
        ├── GitHub OIDC Workload Identity Federation
        └── regional Secret Manager metadata
        ↓
keyless GitHub ↔ Google identity available
        ↓
runtime database user + exact DSN regional secret version
        ↓
other exact regional secret versions
        ↓
regional Cloud Build → immutable image digest
        ↓
private no-traffic Cloud Run candidate
        ↓
one-task/no-retry runtime-control migration
        ↓
/ready = true
        ↓
one-use Gemini canary job + receipt
        ↓
one-use OpenAI canary job + receipt
        ↓
bounded staging load/security/reconciliation receipt
        ↓
final exact-head release evidence
        ↓
ready-for-review → governed merge → post-merge exact-head verification
```

## 1. Prepare a non-template procurement packet

Copy:

```text
config/aigc_external_release_procurement.example.json
```

into a non-repository operator evidence directory.

Set:

- `template_only=false`;
- `release_sha` to the **fresh exact-head SHA actually being released**;
- `release_tree_sha` to that commit's exact Git tree;
- `monthly_budget_cad` to an explicitly reviewed nonzero CAD ceiling;
- at least one existing reviewed Monitoring notification-channel resource name;
- exact Gemini/OpenAI model IDs;
- current reviewed CAD-denominated provider token prices;
- `provider_canary_spend_cad` to the separately reviewed tiny canary ceiling;
- `authority.authorized_by` to the accountable actor;
- `authority.authorized_at` and `authority.expires_at` to a short, explicit execution window.

An executable packet fails closed when the authority window is future-dated or expired. Do not set execution flags merely because values are filled in.

## 2. Read-only Google project/billing discovery

With an authenticated Google Cloud CLI session:

```bash
python scripts/aigc_external_release_procurement.py \
  /secure/aigc/procurement.json \
  --mode discover \
  --output /secure/aigc/discovery.json
```

Require:

```text
project_number_matches = true
billing_link_enabled = true
billing_link_matches = true
```

Discovery performs no resource creation, secret-value access, provider call, or deployment.

If project/billing linkage is wrong, stop. Do not compensate by creating a second unreviewed project.

## 3. Source-control credential preflight

Complete `docs/cloud/QUEBEC_SOURCE_CONTROL_CREDENTIAL_PREFLIGHT.md` through authenticated GitHub account settings. Raw token values are never copied into evidence.

All unresolved classic PAT/deploy-key/webhook/app/session findings remain blocking for cloud authority.

## 4. Bootstrap durable Terraform state

The Québec foundation declares an externally configured GCS backend. Do **not** apply it with ephemeral local state.

First review the exact state bucket target and set only:

```text
authority.state_backend_bootstrap_authorized = true
```

Then execute:

```bash
python scripts/bootstrap_quebec_terraform_state.py \
  --procurement /secure/aigc/procurement.json \
  --execute \
  --output /secure/aigc/terraform-state-receipt.json
```

The state bucket is deterministic:

```text
bucket = <project>-<resource-prefix>-tfstate
prefix = aigc/nexus-v1
location = northamerica-northeast1
```

Required controls are uniform bucket-level access, public-access prevention, object versioning, retention and soft-delete protection. A failed mutation is indeterminate and is not automatically retried.

## 5. Generate the exact material Terraform plan

Review the resource intent, IAM topology, current Google pricing estimate and bounded CAD ceiling. Then set:

```text
authority.terraform_plan_authorized = true
authority.resource_creation_authorized = true
```

`resource_creation_authorized=true` at this phase authorizes the **bounded resource intent represented in the plan**; it does not itself execute Terraform.

Create and retain a saved plan:

```bash
python scripts/terraform_quebec_foundation.py \
  --procurement /secure/aigc/procurement.json \
  --state-receipt /secure/aigc/terraform-state-receipt.json \
  --mode plan \
  --plan-file /secure/aigc/quebec-foundation.tfplan \
  --output /secure/aigc/quebec-foundation-plan-receipt.json
```

The plan receipt binds:

- project / release SHA / release tree;
- procurement digest;
- resource-manifest digest;
- state-backend receipt and bucket/prefix;
- exact saved-plan SHA-256;
- planned resource addresses and action counts.

The current gate rejects destroy and replacement actions.

## 6. Separately authorize and apply only the saved plan

After reviewing the saved-plan receipt and plan output, separately set:

```text
authority.terraform_apply_authorized = true
```

Then execute exactly that saved plan:

```bash
python scripts/terraform_quebec_foundation.py \
  --procurement /secure/aigc/procurement.json \
  --state-receipt /secure/aigc/terraform-state-receipt.json \
  --mode apply \
  --plan-file /secure/aigc/quebec-foundation.tfplan \
  --plan-receipt /secure/aigc/quebec-foundation-plan-receipt.json \
  --output /secure/aigc/quebec-foundation-apply-receipt.json
```

The apply path rejects a moved checkout, changed procurement packet, changed backend receipt, changed plan digest, or destructive plan. A failed apply is `indeterminate`, `reconciliation_required=true`, `automatic_retry=false`.

A successful apply performs read-only post-apply reconciliation and requires WIF, all service accounts, Artifact Registry, private Cloud SQL and regional secret metadata to exist.

The WIF provider is hard-bound to:

```text
repository             = Lornt1666/AIGC
repository_id          = 1287333065
repository_owner_id    = 236225491
allowed refs           = release/aigc-nexus-v1 OR main
issuer                 = https://token.actions.githubusercontent.com
```

The deployer uses `roles/iam.workloadIdentityUser`; no downloadable Google service-account key is created.

## 7. Runtime database credential without Terraform password state

After Cloud SQL and regional Secret Manager metadata exist, run:

```bash
python scripts/bootstrap_nexus_runtime_database_secret.py \
  --procurement /secure/aigc/procurement.json \
  --output /secure/aigc/runtime-db-receipt.json \
  --execute
```

This bootstrap:

1. re-verifies project/billing and Cloud SQL presence;
2. uses Google ADC from the authenticated bootstrap session;
3. generates the runtime database password only in process memory;
4. writes a socket-based DSN to the exact Montréal regional Secret Manager secret;
5. creates `aigc_runtime` through the Cloud SQL Admin API;
6. emits only secret metadata / exact version reference.

If one mutation succeeds without the other, the receipt is `partial` and `reconciliation_required=true`. Do not blind-retry.

## 8. Other exact regional secret versions

Use:

```bash
python scripts/provision_nexus_regional_secret_version.py ...
```

for the remaining governed purposes. Secret values come from operator-controlled local files and are never printed.

For OpenAI, complete the secure OpenAI Platform project-key setup first. Save/copy the value only to a protected local temporary file, then provision it into the `openai_api_key` regional secret. Delete the local temporary copy after the exact-version receipt is verified.

Do not commit an OpenAI key, GitHub token, Google credential, password, Authorization header, or DSN.

## 9. Immutable candidate deployment and runtime migration

Once the exact regional secret inventory is complete and the existing Québec staging authorization passes:

```bash
python scripts/deploy_nexus_staging.py \
  /secure/aigc/quebec-staging-authorization.json \
  /secure/aigc/quebec-resource-manifest.json \
  --execute \
  --output /secure/aigc/deployment-receipt.json
```

The deployer:

- uses regional Cloud Build with the dedicated build service account;
- resolves Artifact Registry to `sha256:<digest>`;
- deploys the immutable digest only;
- disables unauthenticated access and deploys with no production traffic;
- uses Direct VPC egress to the private Québec VPC/subnet;
- attaches private Cloud SQL;
- starts on process `/health` rather than falsely treating an unmigrated DB as ready;
- executes the packaged `003_nexus_provider_runtime_controls.sql` migration through `src.operations.nexus_postgres_migrate` as one task, max retries zero;
- requires a canonical migration receipt;
- only then accepts `/ready=true`.

Any failed mutating Cloud Build / Cloud Run operation is treated as indeterminate and is not automatically retried.

## 10. Prepare exact provider canary requests

Create one `aigc.nexus-provider-canary.v1` JSON plan per provider. It must contain:

- exact provider ID and model;
- exact release SHA;
- principal;
- exact ChangeSet ID and parent-state hash;
- bounded prompt;
- reserved usage units;
- exact maximum CAD cost;
- reviewed current input/output CAD token prices;
- exact runtime-control DSN regional secret version;
- for OpenAI only, exact API-key regional secret version.

Run locally in plan mode:

```bash
python -m src.operations.nexus_provider_canary \
  --plan /secure/aigc/gemini-plan.json \
  --plan-only \
  --output /secure/aigc/gemini-plan-receipt.json
```

Planning performs no provider call.

## 11. Issue canonical live-canary authority

For each provider separately, create/review the canonical `GovernanceDecision` and `ExecutionPermit`.

Required properties:

```text
decision = approved
authority_source = HUMAN
conditions contains exact MAX_COST_CAD=<plan value>
permit capability = generate.text
permit resource_scope contains exact provider://.../model/...
permit exact_revision = plan exact revision
permit request_digest = plan request digest
permit maximum_invocations = 1
```

Gemini and OpenAI receive **different one-use permits**.

## 12. Launch one-task provider canaries

Use the same immutable candidate image and operator identity:

```bash
python scripts/launch_nexus_provider_canary_job.py \
  --procurement /secure/aigc/procurement.json \
  --deployment-receipt /secure/aigc/deployment-receipt.json \
  --plan /secure/aigc/gemini-plan.json \
  --governance /secure/aigc/gemini-governance.json \
  --permit /secure/aigc/gemini-permit.json \
  --output /secure/aigc/gemini-canary-receipt.json
```

Then repeat with independent OpenAI artifacts.

Each job is configured:

```text
tasks = 1
parallelism = 1
max_retries = 0
Direct VPC egress = private-ranges-only
Cloud SQL = private Québec instance
service account = operator
```

The Nexus runtime itself enforces durable permit usage, idempotency, emergency-stop epoch, usage limits and maximum cost. The retained receipt removes provider response text but retains request/result identity, provider request ID, latency, usage, cost, digest, execution receipt and audit counters.

An uncertain provider outcome is not retried.

## 13. Staging validation

After both live canaries succeed, run:

```bash
python scripts/validate_nexus_staging_runtime.py ...
```

Collect authenticated `/health`, `/ready`, metadata-only `/observability`, unauthenticated denial, unknown-route rejection, bounded concurrency and real latency metrics.

Do not introduce destructive fault injection unless it receives a separate exact authorization.

## 14. Release disposition

Only after all external receipts exist:

1. update the final release evidence packet;
2. run fresh PR-triggered exact-head CI;
3. require the retained artifact for that exact SHA;
4. confirm PR #181 remains mergeable and its base has not drifted;
5. mark ready only when the release packet says the blockers are closed;
6. perform the governed merge against the exact expected PR head;
7. require fresh post-merge exact-main verification.

AIGC V1 is not represented as literally zero-defect. Release completion means all declared V1 capabilities and release gates are implemented, tested and backed by the required empirical receipts with no known release-blocking finding.
