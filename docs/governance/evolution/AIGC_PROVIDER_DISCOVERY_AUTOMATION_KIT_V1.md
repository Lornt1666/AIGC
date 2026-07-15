# AIGC Provider Discovery Automation Kit v1

Status: `IMPLEMENTED_INTERNAL_MOCK_ONLY`  
Decision basis: `main@005a3669c86f7eaa1da9559886ea03e786944293`  
Expected readiness movement: `0.00`  
Provider action performed: **No**

## Purpose

Provide an offline-verifiable automation kit for the first provider-discovery workstream without executing Google Cloud commands, issuing an authorization receipt, accessing secret values, changing infrastructure, or representing simulation output as operational evidence.

The kit prepares:

- a validated target-specification submission;
- a deterministic read-only command plan;
- a synthetic mock execution report;
- a non-admissible discovery-evidence candidate;
- a minimal provenance envelope.

It deliberately cannot run live provider commands.

## Canonical artifacts

```text
config/provider_discovery_command_catalog.json
config/provider_discovery_mock_fixture.json
schemas/provider_discovery_command_catalog.schema.json
schemas/provider_discovery_mock_fixture.schema.json
schemas/provider_discovery_simulation_report.schema.json
schemas/evidence_provenance_envelope.schema.json
src/core/provider_discovery_contracts.py
src/core/provider_discovery_automation.py
scripts/run_provider_discovery_mock.py
tests/test_provider_discovery_automation.py
docs/governance/evolution/AIGC_PROVIDER_DISCOVERY_AUTOMATION_KIT_V1.md
.github/workflows/aigc-ci.yml
```

## Execution boundary

The command catalog is permanently configured as:

```text
execution_mode: MOCK_ONLY
shell_execution_allowed: false
live_execution_enabled: false
authorization_receipt_issued: false
provider_action_performed: false
external_action_performed: false
```

The live entry point always raises `ProviderExecutionDisabled`.

Commands are stored as argument arrays, never shell strings. Shell metacharacters, unresolved placeholders, unsupported command prefixes, mutation verbs, secret-version access, and access-token flags fail closed.

## Proposed metadata-only commands

The catalog covers:

```text
gcloud projects describe
gcloud services list --enabled
gcloud projects get-iam-policy
gcloud iam service-accounts list
gcloud iam service-accounts keys list --managed-by=user
gcloud iam workload-identity-pools list
gcloud iam workload-identity-pools providers list
gcloud secrets list
gcloud secrets versions list
gcloud storage buckets describe
```

Every command:

- uses `--format=json`;
- is classified `READ_ONLY`;
- declares `mutation_performed=false`;
- declares `secret_value_access=false`;
- has a bounded timeout;
- has at most three attempts;
- maps to a synthetic fixture key;
- produces digest-bound output summaries.

The catalog does not contain:

```text
gcloud services enable
gcloud secrets versions access
gcloud projects set-iam-policy
gcloud iam service-accounts keys create
gcloud storage buckets create
terraform plan
terraform apply
```

## Manual read-only gates

The following remain manual because this v1 kit does not claim a stable automated command surface for them:

```text
Identity Platform configuration review
OAuth consent and authorized-domain review
billing-linkage review
```

Manual checks may inspect metadata only. They cannot change configuration or copy OAuth client-secret values.

## Target-specification submission

Mock execution produces a schema-valid staging procurement `SUBMISSION` at:

```text
status: TARGET_SPECIFICATION
```

It contains proposed non-secret targets only:

- project ID and project reference;
- WIF pool/provider IDs;
- separate plan/apply/runtime service-account IDs;
- state-bucket reference;
- staging-domain reference;
- canonical GitHub repository, owner, ref, and workflow bindings.

It preserves:

```text
authorization_receipt_issued: false
provider_action_performed: false
terraform_plan_performed: false
terraform_apply_performed: false
external_action_performed: false
```

It does not advance to `DISCOVERY_READY_FOR_REVIEW`.

## Synthetic fixture

The committed fixture is explicitly:

```text
synthetic: true
provider_action_performed: false
external_action_performed: false
```

It contains only fabricated metadata and controlled failure cases. It contains no credential, private key, access token, refresh token, ID token, secret payload, password, authorization header, or OAuth client-secret value.

The fixture intentionally models:

- an existing staging project;
- a partial enabled-API set;
- three synthetic service accounts;
- zero synthetic user-managed keys;
- missing WIF resources;
- missing secret versions;
- a missing state bucket;
- pending manual provider checks.

The expected result is `PARTIAL`, not success.

## Failure handling

The mock runner proves deterministic handling for:

```text
SUCCESS
FAILED
PERMISSION_DENIED
TIMEOUT
MISSING_FIXTURE
```

Timeouts may retry only within the command's declared attempt limit. Permission denial stops immediately. Missing fixture data fails closed. Partial success cannot become provider evidence.

No exception path enables live execution.

## Secret protection

The kit rejects recursively discovered keys such as:

```text
access_token
refresh_token
id_token
private_key
password
secret_value
client_secret_value
authorization_header
credentials
```

It also rejects recognized private-key and provider-token string markers.

Secret Manager commands list secret resources and version metadata only. The `access` operation is prohibited.

## Simulation output

The CLI writes:

```text
target_specification_submission.json
command_plan.json
discovery_simulation_report.json
provenance_envelope.json
```

The report fixes:

```text
execution_mode: MOCK_ONLY
no_network: true
live_execution_attempted: false
authorization_receipt_issued: false
provider_action_performed: false
external_action_performed: false
```

Its evidence candidate fixes:

```text
artifact_kind: SIMULATION_ONLY
admissible_as_provider_evidence: false
provider_read_performed: false
external_action_performed: false
```

Simulation output must never be submitted as a real `provider_discovery_evidence_receipt`.

## Minimal provenance envelope

The envelope records:

```text
node_id
node_type
artifact_digest
repository_revision
created_at
predecessor_ids
authorization_receipt_id
evidence_receipt_id
operator_approval_reference
ci_run_id
rollback_reference
external_action_performed
```

For this kit:

```text
authorization_receipt_id: null
evidence_receipt_id: null
operator_approval_reference: null
external_action_performed: false
```

This is a minimal provenance carrier, not a full evidence graph.

## Determinism

For an identical:

- repository revision;
- catalog;
- fixture;
- target parameters;
- timestamp;

the kit reproduces identical command digests, run ID, target pack ID, simulation report, and provenance envelope.

## CI gates

CI validates:

1. canonical repository contracts;
2. command-catalog schema;
3. mock-fixture schema;
4. AEC-001;
5. committed content including `scripts/` through the redaction scanner;
6. existing procurement smoke stages;
7. provider-discovery mock-only smoke;
8. simulation artifact upload;
9. full repository tests;
10. production-readiness evaluation.

The mock smoke uses the pull-request or push revision as its exact repository binding and performs no network operation.

## Governance

This unit does not authorize:

- Google Cloud discovery;
- credential use;
- workload identity;
- Secret Manager access;
- Terraform planning;
- Terraform apply;
- Identity Platform configuration;
- OAuth configuration;
- DNS mutation;
- test-subject onboarding;
- sign-in;
- deployment.

After admission, the next admissible repository action is to create a real target-specification submission using verified non-secret intended targets. A separate exact-revision, exact-pack, time-bounded discovery authorization remains mandatory before any provider read occurs.
