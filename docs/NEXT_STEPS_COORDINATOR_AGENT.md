# Release Readiness Next-Steps Coordinator

**Agent ID:** `release_readiness_next_steps_coordinator`  
**Contract:** `aigc-next-steps/1.0`  
**Status:** Reference implementation; isolated testing only; not production-ready.

## Purpose

Analyze normalized evidence for an exact 40-character commit SHA, synthesize a deterministic next-action plan, and execute only explicitly registered, allowlisted evidence-gathering actions. The agent is intended to move the AIGC release-readiness workflow forward without waiting for a human to perform routine safe inspections.

## Autonomous action allowlist

- `inspect_exact_head_ci`
- `verify_artifact_binding`
- `run_reference_tests`
- `analyze_gate_evidence`
- `prepare_independent_review_packet`

An action is executed only if both its identifier is allowlisted and a handler is explicitly registered. There are no implicit network or GitHub capabilities. Integrations must be supplied as narrow adapters and independently tested.

## Hard prohibitions

The agent cannot merge, deploy, release, approve a release, approve itself, change the canonical release authority, grant privileges, change branch protection, sign with a private key, spend funds, or contact external parties. Unknown actions and missing handlers fail closed. Handler output fields that could falsely claim approval or authority are removed.

The canonical **Release Assurance Agent** remains the single release decision authority. This coordinator only reports whether all recorded gates are marked PASS and, in that case, emits `ELIGIBLE_FOR_CANONICAL_REVIEW`; it never issues a release decision. A gate is not PASS unless explicit evidence has been recorded. Missing, pending, or unknown gate states block progression.

## Required gate evidence

1. CI for the exact commit.
2. Authenticated binding between commit/tree and generated evidence artifacts.
3. Specification integrity: agent count, contracts, dependency topology, deterministic generation, and FMEA.
4. Independent security/architecture review.
5. Actual isolated deployment and containment validation.
6. Operational acceptance, including timeouts, cancellation, retries, budgets, circuit breakers, and incident response.
7. Explicit human acceptance.
8. Canonical Release Assurance decision on the exact candidate.

## Audit and limitations

The reference records structured in-memory events with a hash chain and avoids storing exception messages. This is not durable or independently authenticated evidence; process-local event storage is not tamper-proof against a process owner. The 30-second asynchronous timeout is not a hard OS-level termination boundary for hostile synchronous/native code. The reference has no real service identity, external queue, deployment integration, or production credentials.

Before production use, implement external workload identity and mTLS, least-privilege per-action credentials, durable append-only audit with external anchoring, process/container isolation, hard execution limits, authenticated artifact provenance, telemetry and SLOs, recovery tests, independent penetration testing, and staged human-approved deployment. Do not supply secrets in task payloads or logs.

## Local validation

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p "test_next_steps_coordinator.py" -v
```

This agent is proposed for integration and testing. It is not deployed, does not override governance, and does not open production gates.
