# AIGC CI Run Verification and Release-Evidence Standard

**Business identity:** RegenExcalibur  
**Owner / accountable product authority:** Justice Gray Maciocha  
**Project:** AIGC — Artificial Intelligence Gladiator Coliseum  
**Document status:** Control standard; implementation conformance must be evidenced separately  
**Release posture:** NOT CERTIFIED; production readiness NOT ESTABLISHED

## 1. Purpose and governing rule

This standard defines how AIGC verifies a CI run and what claims that evidence permits. Standards define the controls. Tests, workflow records, artifacts, and operational observations establish whether the implementation satisfies them.

A green badge alone is insufficient. A CI result proves only the jobs and assertions actually executed by that workflow, against the source revision actually checked out, under the environment and permissions actually used. It does not, by itself, prove runtime end-to-end behavior, deployment safety, legal compliance, or production readiness.

## 2. Evidence vocabulary

Use these states precisely:

- **PASS** — the named check completed successfully and its result is inspectable.
- **FAIL** — the check ran and a required assertion failed.
- **BLOCKED** — the check could not run or could not obtain a required prerequisite.
- **NOT RUN** — no execution evidence exists.
- **UNKNOWN** — evidence is incomplete, contradictory, stale, or cannot establish the outcome.
- **NOT APPLICABLE** — a documented scope decision explains why a control does not apply.
- **VERIFIED** — a specific claim is supported by inspectable evidence bound to its scope and revision.
- **CERTIFIED** — a formally authorized certification decision exists, with defined scope, criteria, assessor, date, and evidence. Do not use this term for ordinary CI success.

Never translate a blocked, skipped, missing, or infrastructure-failed run into PASS. If a job was assigned no runner or executed zero steps, report admission/infrastructure failure, not a code-test failure and not a pass.

## 3. Exact-revision identity gate

Before interpreting a run:

1. Record repository full name, target branch, pull-request number (if applicable), PR head SHA, base SHA, and the exact candidate SHA being evaluated.
2. Open the workflow run and verify its `head_sha` equals the intended candidate SHA. Record the run ID, workflow name/file, event type, run attempt, status, conclusion, actor, and timestamps.
3. Confirm the tested checkout/revision. For pull requests, distinguish the PR head commit from a synthetic merge commit. State which one the workflow tested and which revision the release decision concerns.
4. Confirm the candidate SHA is reachable from the intended PR/branch and has not been superseded.
5. If any source change occurs after the run, the earlier result is historical evidence only; repeat the required checks for the new candidate SHA.
6. Record the workflow definition revision and relevant reusable workflow/action revisions. Prefer immutable action references and pinned dependencies where feasible.

A run is not exact-head evidence if the SHA is unknown, mismatched, or merely inferred from a branch name.

## 4. Run and job verification

For the chosen run and attempt:

1. Require terminal status `completed` and inspect the conclusion. A queued, waiting, in-progress, cancelled, timed-out, action-required, or infrastructure-admission failure is not a passing run.
2. Enumerate every job, including matrix jobs, reusable workflows, and required dependent jobs. Inspect each job's conclusion and steps.
3. Verify that all required jobs actually executed. A skipped job is acceptable only when the workflow's documented conditions and branch-protection policy permit it; do not treat a skipped security or acceptance gate as evidence it passed.
4. Inspect failed and suspicious steps and annotations. For ambiguous failures, inspect job steps and logs; classify the failure as code/test, workflow/configuration, runner/admission, dependency/provider, or evidence-collection failure.
5. Verify required test commands and suites ran, not merely that a generic “validate” command exited zero. Compare the executed test inventory with the requirement-to-test matrix.
6. Inspect artifacts and reports. Confirm they belong to the same run/attempt and candidate SHA; record names, retention, digests where available, and whether they are complete and readable.
7. Confirm the workflow did not silently continue after required failures (for example, through permissive `continue-on-error`, broad exception handling, or an unconditional success step).

A successful workflow conclusion is necessary for a CI pass, but the scope of its tests determines what the pass means.

## 5. Required evidence receipt

Produce a machine-readable receipt for every release-candidate validation. At minimum:

```json
{
  "schema_version": "1.0",
  "repository": "Lornt1666/AIGC",
  "candidate_sha": "<full-commit-sha>",
  "base_sha": "<full-base-sha-or-null>",
  "pull_request": "<number-or-null>",
  "workflow": "<workflow-name-and-file>",
  "run_id": "<github-actions-run-id>",
  "run_attempt": 1,
  "event": "<pull_request|push|workflow_dispatch|merge_group|other>",
  "head_sha": "<run-head-sha>",
  "tested_revision_kind": "<head|merge-commit|other>",
  "status": "completed",
  "conclusion": "<success|failure|cancelled|...>",
  "jobs": [
    {
      "name": "<job-name>",
      "conclusion": "<conclusion>",
      "required": true,
      "steps_executed": true
    }
  ],
  "required_test_inventory": [
    {
      "requirement_id": "<stable-id>",
      "test_or_check": "<name>",
      "result": "<PASS|FAIL|BLOCKED|NOT_RUN|UNKNOWN>",
      "evidence_uri": "<run-log-or-artifact-reference>"
    }
  ],
  "artifacts": [
    {
      "name": "<artifact-name>",
      "sha256": "<digest-or-null>",
      "run_id": "<same-run-id>"
    }
  ],
  "review": {
    "independent_reviewer": "<identity-or-null>",
    "decision": "<approved|changes_requested|pending|not_applicable>",
    "reviewed_sha": "<full-sha-or-null>"
  },
  "limitations": [],
  "production_ready": false,
  "certification_issued": false
}
```

The example is a schema illustration, not an actual receipt. Never populate it with invented values. Store receipts immutably or in an append-only evidence ledger; record the receipt's own digest and provenance. Redact secrets and sensitive runtime data.

## 6. Requirement-to-test traceability

Every mandatory requirement must map to:
- a stable requirement ID and version;
- the control/design statement;
- the code path or configuration enforcing it;
- one or more positive tests;
- negative/adversarial tests for bypasses and failure states;
- the exact CI job/command that runs the tests;
- retained evidence location;
- the responsible reviewer/owner;
- the current result and unresolved gaps.

Use `PASS` only when the relevant test actually ran and its evidence supports the requirement. A test name, test file, configuration value, or planned agent is not evidence of enforcement.

For safety controls, include tests that attempt to bypass the control. For stateful workflows, include concurrency, replay/idempotency, restart/recovery, stale-version, partial-failure, and unknown-outcome cases as applicable.

## 7. AIGC-specific minimum validation layers

These are separate gates; success at one layer does not imply success at another.

### A. Static and contract validation
- schemas and generated artifacts are valid and deterministic;
- configuration and registry references resolve;
- type, lint, dependency, and static-security checks run as specified;
- generated evidence packets match their source inputs and hashes.

### B. Unit and adversarial tests
- malformed or incomplete input fails closed;
- authorization cannot be inferred from packet construction;
- pending, expired, stale, mismatched, or revoked approvals cannot authorize action;
- concurrent/replayed decisions cannot cause duplicate consequential execution;
- timeouts, bounded output, cancellation, and concurrency limits are enforced;
- secret-like values are redacted from logs and artifacts.

### C. Deterministic end-to-end vertical slice
Using a synthetic fixture and no external side effects, prove the actual opportunity-to-deliverable path:
1. ingest fixture;
2. normalize/classify/score;
3. produce assessment dossier;
4. draft deliverable;
5. create a pending authorization packet;
6. prove pending approval produces no execution receipt;
7. independently validate provenance, completeness, schema, and factual claims;
8. emit a final receipt bound to source SHA, fixture digest, output digests, test results, and timestamps.

Repeat the same work order to prove idempotency. Interrupt/restart between phases and prove recovery or explicit UNKNOWN state. Never treat a test of contracts/configuration alone as proof of this vertical slice.

### D. Durable-storage and multi-instance integration
Separately test PostgreSQL and the configured S3-compatible artifact store with two independent app/worker instances. Verify atomic state transitions, leases/admission, idempotency, digest and version checks, restart/task-replacement recovery, denied access, missing objects, stale writes, backend outage, and unknown outcomes. Local fake adapters do not establish real integration behavior.

### E. Deployment and operational verification
Only in an explicitly authorized non-production environment, verify the exact image digest and source SHA, service identity, TLS, authentication on every protected route, readiness/dependency behavior, least privilege, logs/redaction, rollback target, and deployment receipt. A local CI pass does not establish these properties.

## 8. Failure classification and retry policy

Classify before retrying:

- **Code/test failure:** preserve logs; repair the defect; rerun all affected required checks on the new SHA.
- **Runner/admission/billing failure:** record BLOCKED; do not claim tests ran. Retry only after the infrastructure prerequisite is genuinely resolved.
- **Transient provider/dependency failure:** document the dependency and retry policy; avoid uncontrolled retry storms.
- **Artifact/evidence failure:** the run cannot support the affected claim until evidence collection is repaired and revalidated.
- **Unknown or partial execution:** retain UNKNOWN; reconcile from authoritative evidence. Never automatically repeat a consequential action merely because a worker or CI run ended unexpectedly.

Retries create a new attempt or run. Preserve the earlier record; do not overwrite history.

## 9. Release gates

A release candidate may advance only when all applicable gates have evidence:

1. **Source identity:** exact candidate SHA confirmed.
2. **CI:** all required jobs pass for the intended revision.
3. **Requirement coverage:** every mandatory requirement maps to passing evidence or an explicitly approved, non-blocking disposition.
4. **Security:** authorization, isolation, secret handling, abuse limits, and adversarial tests pass.
5. **End-to-end:** the actual deterministic vertical slice passes with retained receipts.
6. **Persistence/recovery:** durability, concurrency, restart, and unknown-outcome behavior are proven for the intended deployment topology.
7. **Independent review:** an authorized reviewer records a decision tied to the exact SHA and evidence digest.
8. **Operational readiness:** monitoring, alerting, backup/restore, rollback, access control, incident response, and dependency readiness are verified.
9. **Legal/governance review:** any required legal acknowledgment is completed by the appropriate parties; an owner-written responsibility notice is not a substitute for legal advice or enforceable terms.
10. **Release authorization:** the authorized decision-maker records an explicit decision bound to the exact candidate and evidence package.

If any mandatory gate is missing, stale, contradictory, or UNKNOWN, the release remains blocked.

## 10. Current known disposition

As of the latest recorded repository evidence in issue #305:

- PR #301 exact-head CI succeeded for `8343851d252ca4c7273f77bc4f0fc02ee6c0b971`, run `39493507457`.
- PR #302 exact-head CI succeeded for `c396e78f2015f72e3087ad64aa561326d445f572`, run `39493350767`.
- Those results establish success only for the configured canonical/Gemini validation path. They do not establish that the Python opportunity-to-deliverable workforce runs end-to-end or that PostgreSQL/S3 integration works.
- Issue #305 requires a deterministic synthetic vertical slice, safety/recovery tests, and evidence receipts.
- Issues #275, #282, #289/#299, and #290 remain release blockers until their acceptance evidence is independently verified.
- Issue #311 identifies a separate safety-control defect: Phase 6 packet construction sets safety booleans true without evidence that the controls ran. This must be remediated and tested; packet construction is not proof of safety verification.

These are historical repository records, not a claim that those runs are the current mainline head. Recheck live PR/run state before any release decision.

**Current disposition: CI evidence exists for specified historical revisions; end-to-end and deployment acceptance remain unproven; certification is not issued; production readiness is not established.**

## 11. Operational checklist

Before recording a CI result:
- [ ] Candidate SHA, PR head SHA, and tested revision kind recorded.
- [ ] Run ID, attempt, workflow revision, event, status, conclusion, and timestamps recorded.
- [ ] Every required job and relevant step inspected.
- [ ] Test inventory reconciled against requirements.
- [ ] Logs, annotations, artifacts, and artifact digests checked.
- [ ] Infrastructure/admission failures distinguished from test failures.
- [ ] Receipt generated from observed values only and retained with provenance.

Before release:
- [ ] All mandatory requirement rows have evidence-backed dispositions.
- [ ] Adversarial and failure-recovery tests pass.
- [ ] End-to-end vertical slice and storage integration evidence are present.
- [ ] Independent review is tied to the exact SHA and evidence digest.
- [ ] Deployment/operational and legal/governance gates are complete.
- [ ] Explicit release decision is recorded.
- [ ] Certification is issued only by the designated authorized process.

## 12. Authoritative references

- GitHub REST API — workflow runs, including filtering by `head_sha`, run status and conclusion: https://docs.github.com/en/rest/actions/workflow-runs
- GitHub Docs — troubleshooting required status checks; checks must correspond to the latest commit SHA: https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- GitHub Docs — branch protection and required status checks: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- AIGC issue #305 — exact-head, zero-cost end-to-end workforce evidence: https://github.com/Lornt1666/AIGC/issues/305
- AIGC issue #275 — command-center security/operability blockers: https://github.com/Lornt1666/AIGC/issues/275
- AIGC issue #282 — durable run/review state: https://github.com/Lornt1666/AIGC/issues/282
- AIGC issue #299 — reconciliation of unknown review decisions: https://github.com/Lornt1666/AIGC/issues/299
- AIGC issue #290 — durable authorization packets and phase evidence: https://github.com/Lornt1666/AIGC/issues/290
- AIGC issue #311 — fail closed on unverified Phase 6 safety assertions: https://github.com/Lornt1666/AIGC/issues/311
