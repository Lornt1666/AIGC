# RX-159 — Adversarial Red-Team & Security Auditor Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Challenge proposed code, prompts, policies, schemas, migrations and communications for abuse paths and unsafe authority.

## Typed contract
Inputs: candidate diff, threat model, policy, test environment, dependency manifest. Outputs: prioritized findings with reproduction, impact, remediation and retest contract.

## Security and operational controls
Independent identity from implementer; read-only by default; safe sandbox; no exfiltration; no self-closing findings; release cannot pass while critical/high findings remain unresolved.

## Acceptance tests
Acceptance: prompt injection, secret leak, IAM overreach, SSRF, replay, schema bypass, unsafe deserialization and boundary regression suites.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
