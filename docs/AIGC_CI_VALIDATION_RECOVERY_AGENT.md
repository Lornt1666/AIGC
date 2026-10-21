# AIGC CI Validation & Recovery Agent

**Mode:** read-only observation and diagnosis. **Release authority:** none. **Default disposition:** BLOCK.

## Purpose and authority boundary

The agent observes GitHub Actions workflow runs, job summaries, step outcomes, sanitized logs, artifact metadata, and stage records. It normalizes those observations into a stable evidence record and proposes minimal repairs for human approval. It does not write to GitHub, edit files, retry workflows, change protected controls, merge, deploy, or override the canonical Release Assurance Agent.

The canonical Release Assurance Agent remains the sole release decision authority. A successful sub-runner is not equivalent to a successful workflow, and an uploaded artifact is not proof that all gates passed.

## Evidence normalization

Every observation records the repository, expected and observed full commit SHA, workflow run ID/status/conclusion, job and step IDs/statuses, artifact IDs/names/digests/expiry, stage IDs/statuses, tested tree SHA, independent-review status, normalized reasons, and explicit false authority flags.

A valid observation requires a completed successful run on the expected full SHA, available unexpired artifact metadata bound to that SHA, no failed steps, successful stage records bound to the same SHA, and authenticated independent review bound to the same SHA. This is a consistency check, not cryptographic verification of downloaded artifact contents.

## Failure diagnosis

The agent classifies observed issues (for example, Python import-path errors, dependency-integrity failures, redaction findings, and failed workflow steps) and produces a bounded, sanitized repair proposal. It must identify the failing stage, relevant evidence identifiers, confidence/limitations, and required approval. It must never propose weakening required checks, scanners, branch protection, signing, provenance, review, or release gates.

## Isolated repair validation

After an authorized human approves a proposal, an implementer may apply it on a new commit. The validation agent must then run the complete canonical workflow on the new exact commit and tree, inspect the complete evidence artifact, and discard all prior-head success evidence. No in-place edits or protected-control changes are made by this observer.

## Fail-closed adversarial cases

Tests cover missing artifacts, stale commit SHA, a forged stage success that conflicts with a failed workflow step, failed/missing independent review, expired artifacts, missing run data, and diagnostic redaction. Any missing, inconsistent, stale, or unverifiable input yields BLOCK.

## Current observed incident

Run [39547586183](https://github.com/Lornt1666/AIGC/actions/runs/39547586183) tested commit `769a03dacdd76dab9dc4f1450d3c6596c0acf8b3`. Dependency installation and the canonical validation runner passed. The Governor integration milestone test step failed because `tests/test_aigc_governor_milestones.py` imports `aigc_governor_milestones`, while the module is under `src/` and that test invocation did not configure the source import path. Subsequent OIDC and security scan steps were skipped. The artifact is present but does not make the overall workflow successful.

**Minimal repair proposal (not applied by this agent):** configure the affected test invocation to resolve the existing `src/` package, for example with a scoped `PYTHONPATH=src`, or use a repository-wide packaging configuration. Preserve all tests and security gates, then rerun the entire canonical workflow on the new commit.

## Implementation status and limitations

This implementation is a pure read-only normalization and triage library. It does not itself call GitHub APIs, download or cryptographically verify artifacts, authenticate reviewers, persist evidence, apply patches, or launch workflows. Those integrations require separately permissioned adapters and authenticated evidence. Until they exist and independent review accepts the implementation, the agent is advisory only and release disposition remains BLOCK.
