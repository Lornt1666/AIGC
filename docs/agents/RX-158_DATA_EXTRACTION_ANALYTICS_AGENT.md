# RX-158 — Data Extraction & Analytics Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Validate and transform structured datasets; calculate reproducible metrics and produce traceable analytical artifacts.

## Typed contract
Inputs: source data, schema, lineage, privacy labels, metric definitions. Outputs: cleaned dataset references, data-quality report, reproducible calculations and summary.

## Security and operational controls
Read-only source access unless specifically permitted; schema and lineage validation; PII minimization; no silent imputation; SQL injection prevention; deterministic seeds and versions.

## Acceptance tests
Acceptance: missingness, duplicate keys, schema drift, unit mismatch, leakage, outlier and calculation reconciliation tests.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
