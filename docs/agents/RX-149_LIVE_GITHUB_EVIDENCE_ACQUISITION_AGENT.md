# RX-149 — Live GitHub Evidence Acquisition Agent

**Lifecycle:** SPECIFIED_NOT_PRODUCTION_INTEGRATED  
**Default:** disabled  
**Authority tier:** R0  
**Release authority:** RX-19 only; this agent has no release authority.

## Mission
Read-only live acquisition of PR metadata, exact head/base SHAs, workflow runs and attempts, jobs, checks, reviews, review threads, and protection readbacks using least-privilege GitHub credentials.

## Typed contract
Inputs: repo, PR number, allowlisted GitHub API base, required check policy. Outputs: timestamped paginated snapshot, per-source completeness, HTTP/API limitations, stable observation digest.

## Security and operational controls
Only GET requests; token from managed environment/secret store; never log credentials; API host allowlist; pagination limits; timeout and retry budget; 403/404 protection state becomes UNVERIFIABLE, never PASS. Must re-fetch head immediately before evaluating candidate evidence.

## Acceptance tests
Acceptance: mocked API tests cover current head, pagination, 403, 404, timeout, malformed payload, wrong host, missing token, and stale SHA. Complete collection or explicit failure; no partial snapshot marked complete.

## Dependencies and failure behavior
- Requires a versioned task/evidence contract, authenticated policy inputs, and append-only audit reference.
- Missing, stale, contradictory, malformed, unauthenticated or out-of-scope inputs return BLOCK or UNVERIFIABLE; never infer success.
- Each invocation is bounded, idempotent where applicable, and emits structured status, evidence references, policy version, timestamps, and correlation ID.
- Production activation requires independent review, passing exact-head CI, approved tool scopes, threat-model review, telemetry, kill-switch test, and explicit authorized human approval.
