# AIGC Nexus V1 External Runtime Procurement Runbook

Status: `REPOSITORY PROCEDURE — NOT RELEASE OR ACCOUNT-MUTATION AUTHORITY`

This runbook closes the gap between the exact-head repository release candidate and the missing external runtime receipts. It does **not** itself grant cloud, provider, spend, deployment, merge, or production authority.

## Verified external identity facts

The currently evidenced non-secret Google account identifiers are:

```text
project_id      = oceanic-base-485407-i7
project_number  = 170151535592
billing_account = 0156E0-2BDD06-7561F1
region          = northamerica-northeast1
```

These identifiers do not prove that the project is currently linked to the
billing account. They also do not prove a nonzero spend permit, WIF, IAM,
service-account, regional-secret, build, registry, Cloud Run, or provider-call
state. The committed procurement example remains `template_only=true`,
zero-spend, and mutation-inert. Copy it outside the repository into an
operator-controlled evidence directory before changing any execution field.

## Architecture

```text
repository repair exact-head CI + independent review
        ↓
governed code merge (not a cloud release)
        ↓
protected-main CI + automatic exact-head admission
        ↓
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
fresh KMS-signed action 0 permit
        ↓
regional Cloud Build → immutable image digest
        ↓
immutable action 0 checkpoint → fresh action 1 permit
        ↓
SBOM + provenance + vulnerability-scan evidence
        ↓
one immutable checkpoint and fresh JIT permit per next action
        ↓
one-task/no-retry runtime-control migration
        ↓
private no-traffic operator and judge candidates
        ↓
separately admitted dormant Gemini/OpenAI canary jobs
        ↓
one-use Gemini and OpenAI execution receipts
        ↓
bounded validation → final no-traffic release evidence
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
python -m scripts.aigc_external_release_procurement \
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
python -m scripts.bootstrap_quebec_terraform_state \
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
python -m scripts.terraform_quebec_foundation \
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
python -m scripts.terraform_quebec_foundation \
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
allowed ref            = refs/heads/main
workflow               = .github/workflows/aigc-release-staging.yml@refs/heads/main
event                   = workflow_dispatch
protected environment  = aigc-nexus-staging
repository visibility  = private
issuer                 = https://token.actions.githubusercontent.com
```

Only the read-only `security_review` identity uses
`roles/iam.workloadIdentityUser`. The repository-defined `deployer` is a
read-only release inspector: it has no build, workload, SBOM, evidence-write,
run, IAM-policy, or runtime-service-account `actAs` permission. This removes the
client-held mutation-plus-`actAs` bypass around signed action permits. No
downloadable Google service-account key is created. A future mutating automation
identity requires a separately reviewed, attached permit-enforcing broker and
new immutable IAM and negative-permission receipts.

## 7. Runtime database credential without Terraform password state

After Cloud SQL and regional Secret Manager metadata exist, use the governed
Omega-X → Ultra-Secrets Agent → Secret Broker workflow. The repository command
below is a read-only discovery/plan surface; `--execute` deliberately fails
before cloud discovery or credential generation:

```bash
python -m scripts.bootstrap_nexus_runtime_database_secret \
  --procurement /secure/aigc/procurement.json \
  --output /secure/aigc/runtime-db-plan.json
```

The Secret Broker must atomically:

1. re-verify project/billing and Cloud SQL presence;
2. generate the runtime database password outside agent-visible memory;
3. create `aigc_runtime` and the socket-based DSN without exposing either value;
4. write the DSN to the exact Montréal regional Secret Manager secret;
5. return a broker-attested receipt containing the enabled numeric version name,
   state, creation time and etag—never the value.

If one mutation succeeds without the other, the receipt is `partial` and `reconciliation_required=true`. Do not blind-retry.

## 8. Other exact regional secret versions

After the broker completes a version, validate its sanitized receipt with:

```bash
python -m scripts.provision_nexus_regional_secret_version \
  --project PROJECT_ID \
  --purpose PURPOSE \
  --secret-id SECRET_ID \
  --broker-receipt /secure/aigc/broker-receipt.json \
  --output /secure/aigc/validated-version-receipt.json
```

The script has no raw-value input and no mutation mode. It validates the exact
project, Montréal location, secret ID, enabled numeric version metadata and
broker attestation digest.

For OpenAI, complete the secure OpenAI Platform project-key setup through the
Secret Broker. Do not copy the key into an agent-visible file or conversation.

Do not commit an OpenAI key, GitHub token, Google credential, password, Authorization header, or DSN.

## 9. Immutable candidate build, migration and no-traffic deployment

Execution requires all of the following before the command is entered:

- a fresh successful exact-head CI admission receipt for the authorized release
  SHA and tree;
- the reviewed Québec staging authorization and exact resource manifest;
- all required enabled Montréal numeric secret-version receipts;
- one fresh, active KMS/RSA-PSS permit for the next exact action only;
- the exact immutable predecessor-checkpoint envelope for every action after
  action 0, with the checkpoint and last action-receipt digests bound into the
  new permit;
- the trusted attached action broker's exact create-only receipt-bucket
  permission; and
- the exact narrowly scoped Artifact Analysis/Cloud Storage permissions needed
  for SBOM export.

The six action names and command order are:

| Index | Action | Required target binding |
|---:|---|---|
| 0 | `cloud_build_submit` | exact immutable release tag |
| 1 | `sbom_export` | signed `verified_predecessor_image_digest` rule; exact digest derived from the verified build receipt |
| 2 | `migration_job_deploy` | exact migration job |
| 3 | `migration_execute` | exact migration-job execution |
| 4 | `operator_deploy` | exact private, no-traffic operator service |
| 5 | `judge_deploy` | exact private, no-traffic judge service |

The CLI executes exactly one action and then stops. Action 0 omits
`--predecessor-checkpoint`:

```bash
python -m scripts.deploy_nexus_staging \
  /secure/aigc/quebec-staging-authorization.json \
  /secure/aigc/quebec-resource-manifest.json \
  --ci-admission /secure/aigc/ci-admission.json \
  --action-permit /secure/aigc/action-00-cloud-build-submit.json \
  --checkpoint-output /secure/aigc/checkpoint-00.json \
  --execute-action
```

For action 1, issue a new permit only after reviewing checkpoint 0, then add
`--predecessor-checkpoint /secure/aigc/checkpoint-00.json` and choose a new
create-only `--checkpoint-output`. Repeat this one-action invocation pattern
through action 5. The terminal invocation also writes
`--deployment-receipt-output`; publication remains a separate permit-gated
operation.

Do not use a guessed digest. The SBOM permit signs the exact immutable URI from
the verified build checkpoint and binds the prior checkpoint object URI,
generation, checkpoint hash, action-receipt hash and action-permit hash. Every
execute permit is newly issued, must already be active, has a total lifetime of
at most 15 minutes and permits exactly one target mutation with no retry. The
permit is atomically burned before dispatch. Exact readback is written to a
create-only remote checkpoint; the next action cannot validate without that
checkpoint. An indeterminate target or checkpoint write requires a separate
zero-mutation reconciliation permit bound to the original consumption record
and action-specific readback hint. It never silently reruns the target.

The authenticated readiness probe requires `roles/run.invoker` on each exact
Cloud Run service IAM policy. A project-level conditional `roles/run.invoker`
binding is not accepted. If the per-service bindings cannot be provisioned
before these actions, add separate permit-gated IAM actions and receipts before
attempting operator/judge deployment; do not fold a second IAM mutation into a
one-mutation service permit.

The current Terraform intentionally cannot execute these six actions: its
`deployer` identity is read-only and cannot impersonate the operator, judge, or
Cloud Build service accounts. Until an attached, non-client-impersonable broker
is reviewed and its exact expiring permissions are receipted, the state remains
`BLOCKED_PENDING_TRUSTED_BROKER` and every execute attempt must stop before
permit consumption.

Once separately authorized, the attached action broker:

- uses regional Cloud Build with the dedicated build service account;
- resolves Artifact Registry to `sha256:<digest>`;
- retains SBOM, signed provenance, scan and registry evidence bound to that
  digest;
- deploys the immutable digest only;
- disables unauthenticated access and deploys with no production traffic;
- uses Direct VPC egress to the private Québec VPC/subnet;
- attaches private Cloud SQL;
- starts on process `/health` rather than falsely treating an unmigrated DB as ready;
- executes the packaged runtime-control migrations through
  `src.operations.nexus_postgres_migrate` as one task, max retries zero;
- requires a canonical migration receipt;
- only then accepts `/ready=true`.

Any failed mutating Cloud Build / Cloud Run operation is treated as indeterminate and is not automatically retried.

## 10. Prepare exact provider canary requests

Create one `aigc.nexus-provider-canary.v2` JSON plan per provider. It must contain:

- exact provider ID and model;
- exact release SHA;
- principal;
- exact ChangeSet ID and parent-state hash;
- bounded prompt;
- reserved usage units;
- exact maximum input and output units plus request timeout;
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

The Gemini V1 canary is fail-closed to the reviewed stable model IDs
`gemini-2.5-flash` and `gemini-2.5-flash-lite`. Its signed resource binding
requires `thinking_budget=0` and `include_thoughts=false`; models for which
thinking cannot be disabled are outside this canary contract. The plan is
rejected unless the worst-case signed input/output token cost fits inside
`maximum_cost_cad`. Provider receipts account for candidate and thinking tokens
separately and reject any unexpected thinking or inconsistent total.

The plan's `location` is the execution region. For Gemini it is also the
validated provider location. For OpenAI, `provider_location` is
`provider-managed`; Montréal execution and a Montréal regional key-secret
version do not establish that OpenAI processing occurs in Montréal.

## 11. Issue canonical live-canary authority and admit dormant jobs

For each provider separately, create/review the canonical `GovernanceDecision` and `ExecutionPermit`.

Required properties:

```text
decision = approved
authority_source = HUMAN
conditions contains exact MAX_COST_CAD=<plan value>
conditions contains exact WORST_CASE_TOKEN_COST_CAD=<computed plan value>
Gemini conditions contain THINKING_DISABLED_REQUIRED=true and THINKING_BUDGET=0
permit capability = generate.text
permit resource_scope contains the exact plan-derived provider://.../bound/<digest>
permit exact_revision = plan exact revision
permit request_digest = plan request digest
permit maximum_invocations = 1
```

Gemini and OpenAI receive **different one-use permits**.

Each provider also requires a separate, short-lived
`aigc.nexus-authority-attestation.v1` signed by the deterministic Montréal KMS
trust root. It binds the procurement, deployment, plan, governance decision,
execution permit, request digest, permit ID, execution nonce and exact derived
job name.

Before the launcher runs, a distinct action-specific authority must have
created and admitted the exact dormant Cloud Run job named by that
attestation. The launcher does not deploy or update jobs. It only describes the
job, verifies its immutable image, dedicated service account, empty dormant
environment, one-task/no-retry bounds, private VPC/Cloud SQL attachments and
labels, and then performs exactly one execution mutation.

The repository now separates this boundary into three receipt-gated actions:

1. `provision_nexus_provider_canary_job.py` may run only as the directly
   attached `<prefix>-can-prov` metadata identity. Terraform leaves its job
   mutation role and runtime `actAs` role inert; an external trusted-broker
   control plane must condition both bindings to the signed provisioning-permit
   expiry. Client impersonation, WIF and service-account keys are rejected.
2. After that broker authority has expired, the directly attached,
   non-impersonable `<prefix>-can-bind` broker burns a KMS-signed one-use
   binding permit and adds one conditional `roles/run.invoker` member to the
   exact dormant job. Its own exact-job `setIamPolicy` condition must expire
   before execution.
3. Only after the binder's `setIamPolicy` authority has expired may that same
   directly attached `<prefix>-can-bind` metadata identity receive a distinct,
   conditional `roles/iam.serviceAccountTokenCreator` grant on
   `<prefix>-can-exec`. The KMS-signed JIT receipt binds `can-bind` as the exact
   source and `can-exec` as the exact target. The launcher refreshes the direct
   Compute metadata credential, verifies its canonical service-account email,
   mints exactly one in-process token capped at 900 seconds and every signed
   expiry, then copies it into a non-refreshing, retry-free REST session. No
   gcloud token, user/workforce ADC, key credential, delegated ADC chain, or
   later automatic refresh is accepted.

Until the two non-impersonable broker runtimes and their conditional IAM
receipts exist, the operational state is `BLOCKED_PENDING_TRUSTED_BROKER`.
Receipt publication uses the distinct `<prefix>-can-pub` identity. It has only
create-only access to the exact receipts bucket and public-key-viewer access to
the deterministic authority key. It has no read/list/update/delete, Cloud Run,
provider, Secret Manager, billing, IAM, `actAs`, WIF or repository-provisioned
TokenCreator grant. Its KMS-signed publication permit must bind the directly
attached `<prefix>-can-bind` metadata identity as `source_principal`; a separate
conditional external grant may target `can-pub` only after all binder mutation
authority has expired. The publisher uses the same one-mint, non-refreshing
token boundary capped at 900 seconds. Until those source-runtime and grant
receipts exist, publication is also `BLOCKED_PENDING_TRUSTED_BROKER`.

## 12. Launch one-task provider canaries

Use the same immutable candidate image. Gemini and OpenAI execute under
different dedicated identities; neither executes as the operator service
account.

```bash
python -m scripts.launch_nexus_provider_canary_job \
  --procurement /secure/aigc/procurement.json \
  --deployment-receipt /secure/aigc/deployment-receipt.json \
  --plan /secure/aigc/gemini-plan.json \
  --governance /secure/aigc/gemini-governance.json \
  --permit /secure/aigc/gemini-permit.json \
  --authority-attestation /secure/aigc/gemini-authority-attestation.json \
  --execution-binding-receipt /secure/aigc/gemini-binding-receipt.json \
  --execution-binding-permit /secure/aigc/gemini-binding-permit.json \
  --jit-impersonation-receipt /secure/aigc/gemini-executor-jit-receipt.json \
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
Gemini service account = <resource-prefix>-can-gem@<project>.iam.gserviceaccount.com
OpenAI service account = <resource-prefix>-can-oai@<project>.iam.gserviceaccount.com
job deployment performed by launcher = false
```

The Nexus runtime itself enforces durable permit usage, idempotency, emergency-stop epoch, usage limits and maximum cost. The retained receipt removes provider response text but retains request/result identity, provider request ID, latency, usage, cost, digest, execution receipt and audit counters.

An uncertain provider outcome is not retried.

## 13. Staging validation

After both live canaries succeed, run the bounded authenticated validation for
each no-traffic candidate. For example:

```bash
python -m scripts.validate_nexus_staging_runtime \
  --project-id PROJECT_ID \
  --service OPERATOR_SERVICE \
  --revision OPERATOR_REVISION \
  --release-sha RELEASE_SHA \
  --image-digest sha256:IMAGE_DIGEST \
  --requests 20 \
  --concurrency 4 \
  --output /secure/aigc/operator-validation-receipt.json
```

Collect authenticated `/health`, `/ready`, metadata-only `/observability`, unauthenticated denial, unknown-route rejection, bounded concurrency and real latency metrics.

Do not introduce destructive fault injection unless it receives a separate exact authorization.

## 14. Release disposition

Code integration and cloud release are distinct transitions. For code
integration:

1. run fresh PR-triggered exact-head CI;
2. require independent repository review and distinct ready/merge authority;
3. confirm the PR head/base identities have not drifted;
4. perform the governed merge without claiming a cloud release;
5. require fresh post-merge exact-main CI;
6. retrieve the automatically assembled, protected-main
   `aigc.exact-head-ci-admission.v2` artifact.

Only after that admission and all external receipts exist may the final packet
mark `RELEASED_NO_TRAFFIC=true`. Production traffic remains a later,
separately authorized transition.

AIGC V1 is not represented as literally zero-defect. Release completion means all declared V1 capabilities and release gates are implemented, tested and backed by the required empirical receipts with no known release-blocking finding.

Current disposition:

```text
fresh_repair_head_ci_admission = NOT_OBSERVED
project_billing_binding = NOT_OBSERVED
nonzero_cad_spend_authority = NOT_PROVISIONED
wif_iam_service_accounts = NOT_OBSERVED
regional_numeric_secret_versions = NOT_OBSERVED
next_jit_staging_action_permit = NOT_ISSUED
staging_action_checkpoints = NONE
sbom_export_least_privilege = NOT_OBSERVED
dormant_canary_jobs = NOT_PROVISIONED_OR_RECEIPTED
cloud_build_and_immutable_digest = NOT_EXECUTED
private_no_traffic_revisions = NOT_EXECUTED
provider_canaries = NOT_EXECUTED
deployed_validation = NOT_EXECUTED
ready_for_review = false
merge_authority = false
production_traffic_authority = false
```
