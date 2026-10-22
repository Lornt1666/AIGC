# AIGC Administrator Protection Readback and Independent Security Review Agents

**Status:** specification only; not production integrated  
**Default disposition:** BLOCK  
**Canonical release decision authority:** RX-19 only  
**Target candidate at design time:** PR #330, head `adc81ff4aed637683a3e9ac07f57f55a85cbe1ad`. This is a historical baseline only; every current task must read the live head and must not reuse stale bindings.

## Agent assignments

| ID | Agent | Responsibilities | Non-delegable boundary |
|---|---|---|---|
| RX-145 | Effective Repository Protection Readback Verifier | Collects authenticated readback for the PR base and release branches; normalizes rulesets, branch protection, required checks, review rules, stale-approval handling, bypass actors, and retrieval metadata; reports discrepancies. | Read-only. Cannot alter protections, infer state from 403/empty results, or claim admin identity without authenticated evidence. |
| RX-146 | Independent Security Reviewer Qualification and Assignment Evidence Coordinator | Defines qualification/conflict checks, assembles evidence for administrator selection, records the administrator's actual assignment, and binds reviewer identity to the reviewed candidate. | Cannot select/assign a human reviewer, invent credentials, assert independence without evidence, submit a human review, or self-approve. The authorized administrator performs assignment. |
| RX-147 | Commit-Bound Security Review and Remediation Evidence Tracker | Tracks human review findings, severity, affected paths, exact commit, remediation SHA, independent retest, disposition, and evidence digests; invalidates stale findings/closures on relevant changes. | Cannot perform or impersonate independent human review, close a finding without independent retest, rewrite review history, or waive a blocker. |

## Required operating sequence

1. Read the live PR head SHA, base branch, target release branch, policy version, and run attempt. Treat missing or contradictory identifiers as BLOCK.
2. RX-145 requests/collates authenticated effective protection readback for both `feat/runtime-governance-harness-v1` and `main`. Capture repository identity, branch identity, administrator identity/authorization evidence, UTC timestamp, source/API or settings-view, effective rule values, required check contexts, approval requirements, stale-review settings, bypass actors, and a canonical digest. A 403, timeout, or empty ruleset listing is **unknown**, never a pass.
3. An authorized repository administrator chooses and assigns a qualified reviewer. RX-146 checks that qualification evidence and a conflict/independence declaration are present, records the actual assignment event, and binds it to the candidate SHA and review scope. Agents may request action but may not make the human assignment.
4. The independent reviewer examines the exact SHA and records findings. RX-147 checks completeness and bindings; it does not author the human's judgment.
5. Each finding is linked to a remediation commit, test evidence, and independent retest. Finding closure is allowed only when a reviewer other than the implementer provides evidence-backed retest and the reviewed candidate is still the same.
6. Any source change invalidates exact-head CI, affected review binding, acceptance binding, and packet digest. Re-run CI and re-review affected changes.
7. Produce a status report and hand the complete evidence packet to RX-19 only after every required gate is authenticated and consistent. RX-19 alone decides release.

## Evidence contract

Minimum fields include: repository, PR number, base/release branch, source commit SHA, tree SHA where available, policy version, administrator identity and authorization, retrieval timestamp, protection evidence source, effective settings, required check contexts, bypass configuration, reviewer identity, qualification basis, conflict declaration, assignment event ID/time, review scope, finding IDs/severity, finding-to-SHA mapping, remediation SHAs, test run IDs/attempts, independent retest identity/result, artifact manifest and digests, evidence packet digest, and invalidation history.

Evidence must be provenance-aware: a file hash alone proves content identity, not who produced or authorized it. Preserve signed/authenticated source receipts where available and independently verify issuer, subject, repository, workflow/event identity, commit SHA, and artifact digest.

## Fail-closed rules

- Default disposition is BLOCK.
- Agents are disabled, R0, and `SPECIFIED_NOT_PRODUCTION_INTEGRATED`.
- Missing, stale, empty, inaccessible, unauthenticated, contradictory, or wrong-commit evidence blocks progression.
- No agent may change repository protections, assign or impersonate a human, claim unsupported reviewer qualifications, self-approve, bypass CI, manufacture acceptance, merge, deploy, or authorize release.
- RX-19 remains the sole release decision authority; evidence completeness is not approval.
- No code-only change can substitute for administrator readback or independent human review.

## Acceptance tests

- 403/empty protection API response remains UNKNOWN/BLOCK.
- Wrong repository, branch, or SHA rejects the readback.
- Missing administrator authorization, timestamp, or digest blocks.
- Missing qualification or conflict declaration blocks reviewer-assignment evidence.
- Implementer-as-reviewer and self-approval are rejected.
- New source commit invalidates review, CI, acceptance, and packet bindings.
- Finding cannot close without remediation plus independent retest evidence.
- Tampered digest, stale run attempt, or inconsistent evidence results in BLOCK.
- Agents never mutate branch settings or create a human review/assignment.
- RX-19 remains the only release decision authority.

## Research basis

- NIST SP 800-218 SSDF v1.1 and the published initial public draft of Rev. 1: https://csrc.nist.gov/pubs/sp/800/218/final and https://csrc.nist.gov/pubs/sp/800/218/r1/ipd
- GitHub protected branches and stale review approvals: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub branch-protection REST permissions/readback: https://docs.github.com/en/rest/branches/branch-protection
- GitHub artifact attestations: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations
- SLSA v1.2 artifact provenance verification: https://slsa.dev/spec/v1.2/verifying-artifacts

The NIST Rev. 1 source cited above is an initial public draft, not a final standard. The agents are specifications until implemented, tested, independently reviewed, and explicitly authorized.
