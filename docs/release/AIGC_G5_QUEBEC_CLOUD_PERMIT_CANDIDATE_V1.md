# AIGC G5 Québec Cloud Permit Candidate V1

Status: `PLAN-STAGE CANDIDATE — PROVIDER DISCOVERY REQUIRED — NOT AUTHORIZED FOR RESOURCE CREATION`

## Purpose

Instantiate the strongest non-mutating G5 artifact possible from current evidence without claiming authenticated Google Cloud state that has not been observed.

## Exact repository binding

The candidate is a child of Nexus V1 PR #181 and binds the exact admitted release:

```text
release_sha = 18e886d48c57b85d8ab8115a6fb765fa6e655fc9
release_tree_sha = 0835d1ec8c57a279c9839bfa207038042e22ed23
AIGC CI #2758 = SUCCESS
```

The tree SHA is recovered from the retained exact-head CI receipt, not guessed from branch metadata.

## Candidate provider identifiers

```text
project_id = oceanic-base-485407-i7
project_number = 170151535592
billing_account_id = 0156E0-2BDD06-7561F1
region = northamerica-northeast1
```

These identifiers are populated from the repository release packet / corroborating account evidence, but their **live project↔billing↔IAM lineage remains unverified** until Issue #210 is executed in an authenticated Google Cloud environment.

## Deterministic resource plan

The manifest uses Terraform's canonical `aigc-qc-stg` prefix and contains only Montréal customer-content resource locations. Global project/IAM/billing/VPC metadata is explicitly classified as `CONTROL_PLANE_METADATA` with `VERIFIED_WITH_LIMITATION`; therefore the package does not claim strict all-metadata Québec residency.

Canonical manifest digest:

```text
sha256 = 837e3337e4b80b4221976b96fb60714d46862ee702a01de93913e497c1c13335
```

## Budget semantics

The permit candidate carries a **proposed maximum ceiling of CAD 200** because that is the bounded maximum already enforced by the Nexus validator/Terraform variables. It is not an assertion that CAD 200 of spend is currently authorized.

Current externally observed budget alerts indicate a `$0.00` Cloud Billing budget, so before staging execution:

```text
pricing_quote_reviewed = true
estimated_monthly > 0
estimated_monthly <= approved ceiling
financial/spend authorization separately satisfied
```

must be evidenced.

Google Cloud budgets are alerting controls, not hard spending caps; the contract retains `budget_is_hard_cap=false`.

## Unresolved provider facts

The candidate deliberately leaves exact Secret Manager version references empty and all review/authority fields false.

Issue #210 must resolve at minimum:

```text
project metadata
project↔billing linkage
enabled APIs
IAM policy
service-account existence
zero user-managed service-account keys
WIF pool/provider metadata
Secret Manager metadata without payload values
state-bucket metadata
Identity Platform / OAuth metadata
pricing estimate
notification channel
```

## Fail-closed state

The candidate passes only the non-mutating `plan` gate.

It is intentionally expected to fail the `staging` gate until:

- provider discovery is complete;
- reviewed cost estimates exist;
- all required review booleans are true;
- exact regional numeric secret-version refs are real;
- configuration is reviewed;
- resource creation is separately authorized;
- staging deployment is separately authorized;
- a bounded authorization time window and exact approval phrase are present.

## Authority boundary

```text
resource_creation_authorized = false
staging_deployment_authorized = false
production_activation_authorized = false
public_access_authorized = false
live_model_call_authorized = false
financial_action_authorized = false
devpost_submission_authorized = false
service_account_key_creation_authorized = false
```

`PLAN CANDIDATE != CLOUD PERMIT != TERRAFORM APPLY != DEPLOYMENT != GEMINI CALL`
