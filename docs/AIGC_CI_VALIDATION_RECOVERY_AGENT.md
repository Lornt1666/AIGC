# AIGC CI Validation & Recovery Agent Suite

Mode: read-only. Default disposition: BLOCK. Canonical release authority: Release Assurance Agent only.

## Agents
1. Canonical Runner vs Overall Workflow Agent separates runner success from complete workflow success.
2. Read-only Observer & Diagnosis Agent normalizes run, job, step, log, artifact, and stage evidence.
3. Fail-Closed Test Agent defines adversarial missing, stale, forged, digest, signature, and review cases.
4. Operating Specification Agent publishes authority boundaries and state rules.
5. Failure Diagnosis & Minimal Repair Agent proposes bounded changes for human approval; never applies them.
6. Validation Status Agent requires both runner and workflow success with no blockers.
7. Current Disposition Agent remains blocked until the acceptance gate is met.
8. Live Monitoring Service reads GitHub Actions metadata, downloads artifacts, verifies SHA-256 against GitHub's advertised digest, checks exact-head receipts, and authenticates reviews using Ed25519.
9. Next Acceptance Gate Agent requires the exact latest SHA, a successful complete workflow, verified artifact, and signed independent review.

## Runner vs workflow
The canonical runner can pass while later tests, scanners, policy gates, or jobs fail. These outcomes are reported separately. Any failed required job or step blocks acceptance.

## Live trust model
Supply a runtime GitHub read token and an independently administered reviewer public-key trust store. Credentials and keys are not stored in the repository. The signed reviewer payload binds reviewer ID, approval, exact SHA, artifact digest, issue time, and expiry. A reviewer name or self-asserted authentication boolean is insufficient.

The service checks archive size, member count/size, path traversal, JSON validity, advertised digest, artifact run SHA, and embedded receipt SHA. Matching GitHub's advertised digest proves byte consistency with that metadata, not independent signed build provenance. Production readiness still requires trusted attestation producer/verifier and separately retained evidence.

## Isolated repair and acceptance
A human approves a patch; the patch is committed as a new SHA; the full canonical workflow reruns on that exact commit/tree; old-head evidence is discarded; the artifact is inspected and digest-verified; and signed independent review is obtained. This suite does not edit source, alter controls, or trigger reruns.

Adversarial cases: runner passes but workflow fails; missing run/job/artifact/receipt/stage; stale SHA; forged stage success; bad digest; expired artifact; malformed JSON; ZIP traversal/resource exhaustion; unknown reviewer; invalid/expired signature; mismatched subject or artifact digest; failed review.

## Current observed run
Run [39548398273](https://github.com/Lornt1666/AIGC/actions/runs/39548398273), commit ba943c833e7ae5e146b83970fd90c7bd76a72c0c, failed. Dependency installation passed, but the canonical runner failed at the redaction stage. Later tests were skipped. Evidence uploaded on failure does not imply workflow success.

Current disposition: VALIDATION_PENDING_RELEASE_BLOCKED.

## Next acceptance gate
1. Inspect the specific redaction finding and propose a minimal text correction without weakening the scanner.
2. Obtain human approval and commit the fix.
3. Complete the full canonical workflow successfully on the new exact SHA.
4. Inspect the artifact; verify digest, receipt, stage records, SHA, tree, and run binding.
5. Obtain an unexpired signed review from a trusted independent reviewer whose public key is provisioned outside the repository.
6. Submit evidence to Release Assurance and record explicit human acceptance. Until then, remain BLOCK.

Limits: Live monitoring needs runtime GitHub read access and an external reviewer trust registry. No auto-patching, reruns, merge, deployment, or release decision is implemented. Hash integrity does not replace authenticated provenance.
