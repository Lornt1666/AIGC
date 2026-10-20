# AIGC Autonomous Release Assurance Agent

## Decision authority and scope

`src/release_assurance_agent.py` is the deterministic decision component for the release gate. It consumes a closed release packet and returns a hash-addressed `APPROVE` or `BLOCK` decision bound to the requested commit and tree. It never deploys, merges, provisions keys, or executes provider actions. A separate least-privilege release controller must enforce its decision and independently recheck the subject before acting. The agent also requires an injected trusted provenance-verifier adapter to cryptographically validate the canonical CI attestation against the expected repository/workflow and subject. If that adapter is absent or fails, the agent blocks. A JSON field claiming CI succeeded is not provenance.

The agent is intentionally not an LLM judge. Language models may summarize failures and propose remediation, but cannot set the verdict, sign evidence, alter required gates, or override a block.

## Required evidence

1. A successful canonical GitHub Actions run for `Lornt1666/AIGC`, with the exact commit SHA, tested Git tree SHA, expected workflow revision, run ID, canonical contract identity/digest, and every required stage receipt.
2. A cryptographically verified GitHub/Sigstore provenance attestation whose subject digest matches the canonical stage-receipt bundle digest. A hash inside unsigned JSON is not a signature and is not sufficient.
3. Valid per-stage canonical receipt digests; each stage must be successful, bound to the same commit/tree/run, and affirm no external action or release authority.
4. Signed, current, action-specific release attestations from distinct trusted issuers for platform policy, AI disclosure, privacy, end-to-end behavior, PostgreSQL/S3 integration, recovery, canary health, rollback drill, and independent review.
5. Exact artifact digest, policy version, checker version, freshness, issuer-to-check authority, and signatures for each attestation.
6. For production, successful canary-health and rollback-drill evidence are mandatory; these checks do not replace the other gates.

## Runtime configuration

Inject `AIGC_RELEASE_EVIDENCE_HMAC_KEYS_JSON`, `AIGC_RELEASE_POLICY_VERSION`, and `AIGC_RELEASE_ISSUER_BY_CHECK_JSON` from an approved secret manager. Never commit secrets or let a model choose a signing key. Keys in tests are synthetic. The included HMAC adapter is a reference implementation; use KMS-backed asymmetric signing and independent key custody for production.

Required checker IDs are: `platform_policy`, `ai_disclosure`, `privacy`, `end_to_end`, `postgres_s3`, `recovery`, `canary_health`, `rollback_drill`, and `independent_review`. Each must map to a distinct issuer. The independent-review attestation records evidence that a qualified independent review occurred; the agent cannot itself perform or impersonate that review.

## Example use

Prepare a JSON packet from actual canonical workflow outputs and signed checker attestations, then run:

```bash
python -c "from pathlib import Path; from src.release_assurance_agent import evaluate_file; print(evaluate_file(Path('release-packet.json'), Path('release-decision.json')))"
```

Missing, malformed, stale, untrusted, mismatched, duplicate or failing evidence produces `BLOCK`. A decision does not constitute deployment approval outside the configured release policy, and it is not proof that the checkers themselves are correct.

## Safety properties and known limitations

- Fail closed on missing trust configuration and required evidence.
- Bind all evidence to exact commit, tree, artifact and release tier.
- Reject non-success canonical CI, incomplete stages, stage tampering, stale policy, invalid signatures and issuer-role mismatch.
- Produce a content-hash-addressed decision with deployment and merge explicitly false.
- The cryptographic provenance-verifier adapter is an explicit mandatory dependency but is not yet implemented or wired to GitHub's attestation verification CLI/API. It must verify both the canonical receipt-bundle attestation and the build/artifact provenance against the exact repository, workflow identity, source commit/tree and artifact digest; verifying only one is insufficient. Until that adapter exists and is independently tested, the agent blocks and cannot open the operational release gate.
- This agent does not yet integrate directly with GitHub Actions, attestations API, KMS, deployment environments, or live canary telemetry. End-to-end acceptance tests are required before it can open an operational production gate.
- No evidence can be manufactured by this agent. No current AIGC release is approved by merely adding this code.
