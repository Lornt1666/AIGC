# AIGC CEO Agent — Action Approval Policy

**Status: IMPLEMENTATION DRAFT — NOT A PRODUCTION AUTHORITY.**

## Purpose

The CEO Agent is a deterministic, policy-bound approval gate for proposed AIGC actions. It decides whether a request is eligible for a narrow, low-risk approval, must be held for missing or untrusted evidence, or requires explicit human authorization. It does not execute actions, grant permissions, spend money, modify repositories, deploy, merge, or release.

## Approval boundary

The CEO Agent may return `APPROVE` only for the explicit allowlist `regenerate_internal_index`, `generate_documentation_draft`, `rebuild_local_report`, `run_offline_validation`, or `format_generated_document`, and only when all conditions hold. Unknown action types require human authorization.

- The request and envelope bind to the same repository, full commit SHA, full tree SHA, policy digest, and invocation ID.
- Each evidence item declares an authenticated status, evidence reference, and matching version bindings. In production, the status must be produced by the independently configured trusted verifier, not accepted from untrusted user input.
- The action is explicitly low-risk, reversible, internal-only, and zero-cost.
- The action does not access secrets, change permissions, or have external effects.
- An independent review is recorded.

Missing or inconsistent version bindings, absent evidence, unauthenticated evidence, and absent independent review result in `HOLD`. Medium/high/critical risk, non-reversible actions, cost, external effects, merge, release, deployment, secret access, permission changes, and other consequential operations return `REQUIRES_HUMAN`.

## Separation of duties

- **CEO Agent:** policy decision for bounded action requests; never executes the action.
- **Execution controller:** separately enforces allowed actions and independently checks the decision receipt before execution.
- **Evidence producers:** produce evidence but cannot assert trust by themselves.
- **Independent verifier:** authenticates signer identity, signature, evidence references, and exact-version bindings.
- **Human approver:** explicitly accepts consequential actions through an authenticated approval mechanism.
- **Canonical Release Assurance Agent:** remains the sole release decision authority.

The CEO Agent cannot approve its own implementation, override a policy, bypass required human acceptance, or replace canonical Release Assurance.

## Receipt semantics and limitations

The JSON receipt includes a request digest and a self-excluding receipt digest for integrity comparison. These SHA-256 digests are **not signatures**, do not establish the identity of the approver, and do not make an input evidence record trustworthy. The current implementation checks a supplied `authentication_status` field; therefore production wiring MUST populate that field only from a verified, authenticated evidence store or trusted verifier API. It must never trust a caller-provided Boolean or string as proof of authentication.

The current CLI is an offline policy evaluator. It is not connected to GitHub branch protection, a cloud KMS, an immutable evidence store, a human identity provider, or an action executor. Production activation is blocked until those integrations and independent tests are complete.

## CLI

```bash
python src/aigc_ceo_agent.py --request request.json --envelope envelope.json --output receipt.json
```

Exit code 0 means the bounded policy returned `APPROVE`; exit code 2 means the decision is not an approval. A successful policy evaluation does not mean an action was executed.

## Required production acceptance gates

1. Replace caller-supplied evidence status with a direct verifier/store integration.
2. Authenticate approver identity and record approval scope, expiry, nonce, and replay protection.
3. Bind receipt to a canonical action plan and exact tested source/tree.
4. Have an execution controller enforce the approved action allowlist and refuse mismatches.
5. Store receipts and evidence in separately administered, retention-locked storage.
6. Independently review the policy and threat model; run positive and negative integration tests.
7. Preserve explicit human approval for all consequential actions and canonical Release Assurance for releases.
