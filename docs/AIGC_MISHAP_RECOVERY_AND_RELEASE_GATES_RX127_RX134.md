# AIGC Mishap Recovery and Release-Gate Operations — RX-127–RX-134

**Status:** specification and registry contracts added; operational activation not authorized  
**Default disposition:** BLOCK  
**Release authority:** RX-19 only  
**Scope:** failure diagnosis, safe recovery, exact-head evidence, independent review, repository protection, authenticated acceptance, provenance, and readiness handoff.

## Agent responsibilities

| Agent | Operational responsibility | Hard boundary |
|---|---|---|
| RX-127 Runtime Incident Triage and Safe Recovery | Preserve evidence, classify severity/blast radius, coordinate containment and reversible recovery | No destructive remediation before evidence capture; cannot declare resolution without proof |
| RX-128 CI Failure Root-Cause and Regression Diagnosis | Correlate SHA/run attempt/job/step/logs/tests/artifacts; separate facts from hypotheses; produce reproduction and falsification tests | Cannot suppress tests or label an unproven cause as confirmed |
| RX-129 Exact-Head CI and Artifact Forensics | Verify exact SHA, workflow attempt, required jobs, skipped stages, artifact digests and test summary | Stale, mismatched, incomplete, or failed evidence blocks |
| RX-130 Crash, Retry, and Recovery Verification | Test timeout/crash/partial-side-effect/replay/cancellation/rollback paths | Unknown external outcome requires reconciliation; never blindly retry |
| RX-131 Independent Review and Findings Closure Coordinator | Track administrator-assigned reviewer, independence, commit-bound findings, remediation and retests | Cannot assign or impersonate human reviewers or self-close findings |
| RX-132 Repository Protection and Merge-State Readback | Coordinate authorized branch/ruleset/required-check readback and verify merge state | Permission failure is unresolved evidence, not proof that protection exists or is absent |
| RX-133 Authenticated Acceptance and Provenance Evidence | Verify acceptance binding, signed post-merge provenance and independent artifact retrieval | Cannot fabricate acceptance, identity, signature or provenance |
| RX-134 Operational Readiness and Incident Learning Orchestrator | Consolidate incident, SLO, rollback, review, provenance and open-blocker evidence for RX-19 | Cannot enable agents, merge, or authorize release |

## Mandatory operating sequence

1. **Detect and preserve — RX-127.** Capture exact commit, branch/base, run ID and attempt, job/step IDs, timestamps, failure logs, artifact IDs/digests, environment versions, and impact. Redact secrets; preserve original evidence read-only.
2. **Diagnose and reproduce — RX-128.** Distinguish directly observed facts from hypotheses. For each hypothesis, state supporting evidence, counter-evidence, confidence, and the cheapest discriminating reproduction/falsification test. A log message occurring near a failure is not proof of causation.
3. **Verify exact-head evidence — RX-129.** Ensure the run's observed SHA equals the candidate SHA, all required jobs finished, required stages did not silently skip, test counts and artifacts are inspected, and the attempt is identified. A rerun of a stale SHA never validates a newer commit.
4. **Repair and prove recovery — RX-130.** Make the smallest safe change that addresses the demonstrated cause. Add a regression test. Exercise failure injection, replay, timeout, crash and rollback paths. Record uncertain external side effects as UNKNOWN; reconcile before any retry. Never remove or weaken an assertion merely to obtain a green run.
5. **Independent human review — RX-131.** An authorized repository administrator assigns a qualified independent human reviewer. Bind every finding to the reviewed SHA; record remediation commits and evidence-backed retests. AI agents provide analysis but are not the independent reviewer.
6. **Protection readback — RX-132.** Obtain administrator-authorized readback of required checks, branch/ruleset restrictions, reviewer requirements, and bypass permissions. If permissions prevent readback, leave the gate unresolved and blocked.
7. **Acceptance and provenance — RX-133.** Verify authenticated human acceptance is cryptographically or otherwise verifiably bound to the exact final SHA and evidence-manifest digest. After authorized merge, verify signing identity, attestation claims, provenance, and independent retrieval of retained evidence.
8. **Operational readiness and RX-19 handoff — RX-134.** Summarize completed evidence, open findings, SLO/telemetry status, runbooks, rollback rehearsal, remaining risk, and gate decisions. Send the complete evidence packet to RX-19, the sole canonical release decision authority.

## Minimum incident record

Each incident/remediation record should contain:
- Unique incident ID, severity, detection time, affected components, owner, and status.
- Exact source SHA, base SHA, workflow run ID/attempt, job/step identifiers, and immutable log/artifact references.
- Observed failure signature and redacted evidence digest.
- Root-cause statement with confidence, evidence, alternatives considered, and falsification result.
- Remediation commit, regression-test reference, exact-head validation receipt, and before/after outcome.
- Recovery/rollback test result and reconciliation record for uncertain side effects.
- Reviewer assignment/identity evidence, finding IDs and retests, administrator protection readback, authenticated acceptance receipt, provenance digest, and retention retrieval receipt as applicable.

## Anti-mishap invariants

- Never delete, rewrite, or conceal failed evidence to make a run appear successful.
- Never weaken or skip a required test to obtain a pass.
- Never change a root-cause label from hypothesis to confirmed without discriminating evidence.
- Never retry an uncertain side effect until it has been reconciled or proven safe to retry.
- Never treat a workflow success on an old SHA as validation of a new SHA.
- Never infer repository protection state from a 403, 404, unavailable connector, or permission error.
- Never treat a chat statement, bot comment, or agent-generated record as authenticated acceptance.
- Any new source, test, workflow, policy, or relevant configuration commit invalidates dependent exact-head evidence.
- Missing, stale, contradictory, unauthorized, or unverifiable evidence yields BLOCK.
- No agent can self-enable, self-approve, assign a human identity, bypass protection, merge, or authorize release.

## Current known incident context

The prior CI attempt #39780164587 failed, and its rerun also ended in failure. Logs included PostgreSQL errors involving duplicate key command_center_one_active_run and a rejected invalid-state value against command_center_runs_status_check. These observations are not, by themselves, a confirmed root cause of the canonical validation failure. RX-128 must locate the exact failing step/assertion and obtain a discriminating reproduction before proposing a fix. The failed run's artifact is failure evidence, not a passing release receipt.

The last known successful runtime-maturity test run was #39780888505 on SHA 9b07abefe888e7b7b363f75b2b748c3e41de3484. Subsequent commits to add RX-127–RX-134 mean that success does not validate the current branch head. A fresh exact-head CI run is mandatory.

## Activation policy

RX-127–RX-134 are currently disabled, R0, and specification-only. Enable only the minimum necessary agent after implementation, contract/negative/failure-injection tests, least-privilege identity, independent review, rollback rehearsal, and authorized human activation are evidenced. This document does not authorize runtime execution or production access.
