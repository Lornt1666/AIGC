# AIGC Product Evidence

This directory is an evidence index, not proof of production by itself.

Do not commit credentials, raw customer identifiers, private financial records,
or unredacted model inputs/outputs.

## Evidence states

- `offline_contract_smoke`: CI-only structural validation. It performs no
  Gemini/model API call, external business action, deployment, customer
  interaction, or production run.
- `staging_runtime`: a redacted staging record tied to an exact revision and
  deployment receipt.
- `production_runtime`: a redacted record produced by the deployed application
  using the configured Vertex AI Gemini model and durable Cloud Storage evidence
  backend.

## Required production evidence before a submission claim

1. Exact release revision and immutable container image digest.
2. Cloud Run deployment and service identity receipt.
3. Vertex AI model name, location, response ID where available, token usage,
   latency, correlation ID, and `model_api_call_performed: true`.
4. Redacted opportunity input hash and validated assessment hash.
5. Deterministic policy outcome.
6. Human approve, deny, or revise evidence.
7. `external_business_action_performed: false`. A Gemini API call is a provider
   interaction and must be recorded separately; it is not an external business
   action.
8. Consent and privacy review for any customer-derived material.

Copy reviewed, redacted evidence here only after it has been verified against
the durable runtime source. Never describe the offline smoke artifact as live
Gemini or production evidence.

The code uses a create-only Cloud Storage precondition and per-record integrity
hash. Do not describe that as tamper-proof or regulatorily immutable without
separate evidence of bucket retention policy, IAM, and audit logging.
